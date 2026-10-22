//! MPEG Layer III with an optional ID3v2.3/2.4 tag.
//!
//! Three duration rules, each the one ffmpeg applies and checked against ffprobe on the
//! generated corpus: a Xing/Info frame (frame count, minus the LAME gapless trim), a VBRI
//! frame (frame count), and, without any index, the byte length of a stream whose frames
//! all share one bitrate. A stream whose bitrate varies and has no index is estimated by
//! ffmpeg from the packets it happened to probe: not reproduced, so it uses the reference.

use crate::audio::{
    ambiguous, corrupt, cover_error, insert, limit, read_exact, unsupported, Duration, Layout,
    Picture, Result, MAX_METADATA_BYTES, MAX_TEXT_BYTES,
};
use crate::COVER_BYTES;
use std::collections::HashSet;
use std::io::{Read, Seek, SeekFrom};

fn syncsafe(bytes: &[u8]) -> Result<usize> {
    if bytes.len() != 4 || bytes.iter().any(|byte| byte & 0x80 != 0) {
        return Err(corrupt());
    }
    Ok(bytes
        .iter()
        .fold(0, |size, byte| (size << 7) | usize::from(*byte)))
}

fn decode_text(bytes: &[u8]) -> Result<String> {
    let (&encoding, bytes) = bytes.split_first().ok_or_else(corrupt)?;
    let text = match encoding {
        0 => bytes.iter().map(|byte| char::from(*byte)).collect(),
        3 => String::from_utf8(bytes.to_vec()).map_err(|_| corrupt())?,
        1 | 2 => {
            let (little, bytes) = if encoding == 1 {
                if bytes.starts_with(&[0xff, 0xfe]) {
                    (true, &bytes[2..])
                } else if bytes.starts_with(&[0xfe, 0xff]) {
                    (false, &bytes[2..])
                } else {
                    return Err(unsupported());
                }
            } else {
                (false, bytes)
            };
            if bytes.len() % 2 != 0 {
                return Err(corrupt());
            }
            let units = bytes.as_chunks::<2>().0.iter().map(|unit| {
                if little {
                    u16::from_le_bytes([unit[0], unit[1]])
                } else {
                    u16::from_be_bytes([unit[0], unit[1]])
                }
            });
            char::decode_utf16(units)
                .collect::<std::result::Result<String, _>>()
                .map_err(|_| corrupt())?
        }
        _ => return Err(unsupported()),
    };
    // A trailing terminator is ordinary; multiple text values need an explicit merge policy.
    let text = text.trim_end_matches('\0').to_owned();
    if text.contains('\0') {
        return Err(ambiguous());
    }
    Ok(text)
}

/// APIC: text encoding, Latin-1 MIME type, picture type, description, image bytes.
fn apic(data: &[u8]) -> Result<Picture> {
    let (&encoding, rest) = data.split_first().ok_or_else(corrupt)?;
    if !matches!(encoding, 0..=3) {
        return Err(unsupported());
    }
    let end = rest
        .iter()
        .position(|byte| *byte == 0)
        .ok_or_else(corrupt)?;
    let mime: String = rest[..end].iter().map(|byte| char::from(*byte)).collect();
    // Picture type, then a description whose terminator depends on the encoding.
    let rest = rest.get(end + 2..).ok_or_else(corrupt)?;
    let wide = matches!(encoding, 1 | 2);
    let mut at = 0;
    loop {
        let step = if wide { 2 } else { 1 };
        let unit = rest.get(at..at + step).ok_or_else(corrupt)?;
        at += step;
        if unit.iter().all(|byte| *byte == 0) {
            break;
        }
    }
    Ok(Picture {
        declared: Some(mime),
        data: rest[at..].to_vec(),
    })
}

/// What one MPEG audio frame header announces.
#[derive(Clone, Copy, PartialEq, Debug)]
struct Frame {
    /// MPEG-1 (true) or MPEG-2/2.5 (false): Layer III only.
    mpeg1: bool,
    mono: bool,
    bitrate: u64,
    rate: u64,
    samples: u64,
    length: u64,
    protected: bool,
    version_bits: u8,
    bitrate_index: u8,
    rate_index: u8,
}

const BITRATES_MPEG1: [u64; 15] = [
    0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320,
];
const BITRATES_MPEG2: [u64; 15] = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160];

fn parse_frame(header: [u8; 4]) -> Option<Frame> {
    // Sync, Layer III, and a version, bitrate and rate the standard defines. Free format
    // (bitrate index 0) has no announced length: outside the subset.
    if header[0] != 0xff || header[1] & 0xe0 != 0xe0 || header[1] & 6 != 2 {
        return None;
    }
    let version_bits = (header[1] >> 3) & 3;
    let mpeg1 = match version_bits {
        3 => true,
        0 | 2 => false,
        _ => return None,
    };
    let bitrate_index = header[2] >> 4;
    let rate_index = (header[2] >> 2) & 3;
    if bitrate_index == 0 || bitrate_index == 15 || rate_index == 3 {
        return None;
    }
    let rate = match (version_bits, rate_index) {
        (3, 0) => 44_100,
        (3, 1) => 48_000,
        (3, 2) => 32_000,
        (2, 0) => 22_050,
        (2, 1) => 24_000,
        (2, 2) => 16_000,
        (0, 0) => 11_025,
        (0, 1) => 12_000,
        _ => 8_000,
    };
    let bitrate = 1000
        * if mpeg1 {
            BITRATES_MPEG1[usize::from(bitrate_index)]
        } else {
            BITRATES_MPEG2[usize::from(bitrate_index)]
        };
    let padding = u64::from((header[2] >> 1) & 1);
    let length = if mpeg1 { 144 } else { 72 } * bitrate / rate + padding;
    Some(Frame {
        mpeg1,
        mono: header[3] >> 6 == 3,
        bitrate,
        rate,
        samples: if mpeg1 { 1152 } else { 576 },
        length,
        protected: header[1] & 1 == 0,
        version_bits,
        bitrate_index,
        rate_index,
    })
}

impl Frame {
    /// The properties that must not change along a stream with a constant bitrate.
    fn same_stream(&self, other: &Frame) -> bool {
        self.version_bits == other.version_bits
            && self.bitrate_index == other.bitrate_index
            && self.rate_index == other.rate_index
            && self.mono == other.mono
    }
}

pub(crate) fn scan<R: Read + Seek>(
    reader: &mut R,
    file_len: u64,
    want_cover: bool,
) -> Result<Layout> {
    if file_len < 16 {
        return Err(corrupt());
    }
    // ID3v1/APE coexistence is deliberately not merged with ID3v2.
    let tail_len = file_len.min(160) as usize;
    reader
        .seek(SeekFrom::End(-(tail_len as i64)))
        .map_err(|_| corrupt())?;
    let mut tail = vec![0; tail_len];
    read_exact(reader, &mut tail)?;
    if (tail_len >= 128 && &tail[tail_len - 128..tail_len - 125] == b"TAG")
        || tail.windows(8).any(|chunk| chunk == b"APETAGEX")
    {
        return Err(ambiguous());
    }
    reader.rewind().map_err(|_| corrupt())?;
    let mut header = [0; 10];
    read_exact(reader, &mut header)?;
    let mut layout = Layout::default();
    let mut audio_offset = 0;
    if &header[..3] == b"ID3" {
        let version = header[3];
        if !matches!(version, 3 | 4) || header[4] != 0 || header[5] != 0 {
            return Err(unsupported());
        }
        let size = syncsafe(&header[6..10])?;
        if size > MAX_METADATA_BYTES {
            return Err(limit());
        }
        if size as u64 + 14 > file_len {
            return Err(corrupt());
        }
        let mut content = vec![0; size];
        read_exact(reader, &mut content)?;
        let mut cursor = 0;
        let mut seen = HashSet::new();
        while cursor < content.len() {
            if content[cursor..].iter().all(|byte| *byte == 0) {
                break;
            }
            if content.len() - cursor < 10 {
                return Err(corrupt());
            }
            let frame = &content[cursor..cursor + 10];
            if frame[..4]
                .iter()
                .any(|byte| !byte.is_ascii_uppercase() && !byte.is_ascii_digit())
                || frame[8..10] != [0, 0]
            {
                return Err(unsupported());
            }
            let size = if version == 4 {
                syncsafe(&frame[4..8])?
            } else {
                u32::from_be_bytes(frame[4..8].try_into().map_err(|_| corrupt())?) as usize
            };
            let end = cursor
                .checked_add(10)
                .and_then(|start| start.checked_add(size))
                .filter(|end| *end <= content.len())
                .ok_or_else(corrupt)?;
            let key = match &frame[..4] {
                b"TIT2" => "title",
                b"TPE1" => "artist",
                b"TALB" => "album",
                b"TPE2" => "album_artist",
                b"TRCK" => "track",
                b"TPOS" => "disc",
                b"TDRC" | b"TYER" => "date",
                b"TCON" => "genre",
                b"TSSE" => "encoder",
                b"APIC" => "picture",
                _ => return Err(unsupported()),
            };
            let data = &content[cursor + 10..end];
            if key == "picture" {
                // Pictures never change the tags: several are only a cover ambiguity.
                if data.len() > COVER_BYTES {
                    return Err(limit());
                }
                layout.add_picture(want_cover, || apic(data).map_err(cover_error))?;
            } else {
                if !seen.insert(key) {
                    return Err(ambiguous());
                }
                if data.len() > MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let value = decode_text(data)?;
                if key == "genre"
                    && (value.starts_with('(')
                        || value.chars().any(|character| character.is_ascii_digit()))
                {
                    return Err(ambiguous());
                }
                if key != "encoder" {
                    insert(&mut layout.tags, key, value)?;
                }
            }
            cursor = end;
        }
        audio_offset = 10 + size as u64;
    }
    reader
        .seek(SeekFrom::Start(audio_offset))
        .map_err(|_| corrupt())?;
    let mut audio = [0; 4];
    read_exact(reader, &mut audio)?;
    // MPEG Layer III only, not a file disguised by its extension or leading junk.
    if audio[0] != 0xff || audio[1] & 0xe0 != 0xe0 || audio[1] & 6 != 2 {
        return Err(corrupt());
    }
    let first = parse_frame(audio).ok_or_else(|| {
        // A reserved value is corrupt; free format and the other exotic cases are not reproduced.
        if audio[2] >> 4 == 0 {
            unsupported()
        } else {
            corrupt()
        }
    })?;
    // ffmpeg locates the index after the 4-byte header and the side information, without
    // accounting for the 2-byte CRC of a protected frame; it then finds none.
    if first.protected {
        return Err(unsupported());
    }
    let side_info = match (first.mpeg1, first.mono) {
        (true, true) => 17,
        (true, false) => 32,
        (false, true) => 9,
        (false, false) => 17,
    };
    reader
        .seek(SeekFrom::Start(audio_offset + 4 + side_info))
        .map_err(|_| corrupt())?;
    let mut index = [0; 4];
    read_exact(reader, &mut index)?;
    if matches!(&index, b"Xing" | b"Info") {
        layout.duration = Duration::Checked(xing_duration(reader, first.samples, first.rate)?);
        return Ok(layout);
    }
    reader
        .seek(SeekFrom::Start(audio_offset + 36))
        .map_err(|_| corrupt())?;
    read_exact(reader, &mut index)?;
    if &index == b"VBRI" {
        layout.duration = Duration::Exact(vbri_duration(reader, first.samples, first.rate)?);
        return Ok(layout);
    }
    // No index: the reference estimates from the bitrate and the bytes, which is exact only
    // when every frame announces that bitrate.
    let total = file_len - audio_offset;
    if total > crate::audio::MAX_CHAIN_BYTES {
        return Err(limit());
    }
    reader
        .seek(SeekFrom::Start(audio_offset))
        .map_err(|_| corrupt())?;
    chain(reader, total, &first)?;
    layout.duration = Duration::Exact(total as f64 * 8.0 / first.bitrate as f64);
    Ok(layout)
}

/// Walk the frames from the current position to the end: all of the same stream, the last
/// one complete, nothing after it.
fn chain<R: Read>(reader: &mut R, total: u64, first: &Frame) -> Result<u64> {
    let mut frames = 0;
    let mut position = 0_u64;
    let mut header = [0_u8; 4];
    let mut have = 0;
    let mut skip = 0_u64;
    let mut buffer = vec![0_u8; 64 * 1024];
    loop {
        if position == total && have == 0 && skip == 0 {
            return Ok(frames);
        }
        let count = reader.read(&mut buffer).map_err(|error| {
            if error.kind() == std::io::ErrorKind::Other {
                limit()
            } else {
                corrupt()
            }
        })?;
        if count == 0 {
            return Err(corrupt());
        }
        let mut at = 0;
        while at < count {
            if skip > 0 {
                let take = (skip as usize).min(count - at);
                skip -= take as u64;
                at += take;
                position += take as u64;
                continue;
            }
            if position == total {
                // More bytes than the opened length: the file is changing.
                return Err(unsupported());
            }
            header[have] = buffer[at];
            have += 1;
            at += 1;
            position += 1;
            if have == 4 {
                let frame = parse_frame(header).ok_or_else(unsupported)?;
                if !frame.same_stream(first) {
                    return Err(unsupported());
                }
                skip = frame.length - 4;
                frames += 1;
                have = 0;
                if position + skip > total {
                    // A truncated final frame: ffmpeg's estimate is not worth reproducing.
                    return Err(unsupported());
                }
            }
        }
    }
}

/// VBRI (Fraunhofer): version 1, delay, quality, byte count, frame count.
fn vbri_duration<R: Read>(reader: &mut R, samples_per_frame: u64, sample_rate: u64) -> Result<f64> {
    let mut fields = [0; 14];
    read_exact(reader, &mut fields)?;
    let version = u16::from_be_bytes([fields[0], fields[1]]);
    let frames = u64::from(u32::from_be_bytes([
        fields[10], fields[11], fields[12], fields[13],
    ]));
    if version != 1 || frames == 0 {
        return Err(unsupported());
    }
    Ok((frames * samples_per_frame) as f64 / sample_rate as f64)
}

/// Duration the reference (ffmpeg/ffprobe) reports for an MP3 with a Xing/Info frame.
///
/// The frame count is mandatory: without it ffmpeg falls back to a bitrate estimate that
/// this crate does not reproduce. Encoders named LAME, Lavf or Lavc add a 12-bit start
/// delay and a 12-bit end padding, which ffmpeg subtracts from the total; any other
/// encoder string leaves the plain `frames * samples_per_frame` count. Both rules were
/// checked against ffprobe on 148 generated files and on edited copies of one of them.
fn xing_duration<R: Read>(reader: &mut R, samples_per_frame: u64, sample_rate: u64) -> Result<f64> {
    let mut word = [0; 4];
    read_exact(reader, &mut word)?;
    let flags = u32::from_be_bytes(word);
    if flags & 1 == 0 {
        return Err(unsupported());
    }
    read_exact(reader, &mut word)?;
    let frames = u64::from(u32::from_be_bytes(word));
    if frames == 0 {
        return Err(unsupported());
    }
    let mut skip = [0; 100];
    if flags & 2 != 0 {
        read_exact(reader, &mut word)?;
    }
    if flags & 4 != 0 {
        read_exact(reader, &mut skip)?;
    }
    if flags & 8 != 0 {
        read_exact(reader, &mut word)?;
    }
    // Encoder (9), revision, lowpass, replay gain (8), flags, bitrate, then 3 delay bytes.
    let mut lame = [0; 24];
    read_exact(reader, &mut lame)?;
    let total = frames.checked_mul(samples_per_frame).ok_or_else(corrupt)?;
    let samples = if matches!(&lame[..4], b"LAME" | b"Lavf" | b"Lavc") {
        let delays = u32::from_be_bytes([0, lame[21], lame[22], lame[23]]);
        let trim = u64::from(delays >> 12) + u64::from(delays & 0xfff);
        if trim >= total {
            return Err(corrupt());
        }
        total - trim
    } else {
        total
    };
    Ok(samples as f64 / sample_rate as f64)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn text_values_reject_invalid_and_ambiguous_encodings() {
        assert_eq!(decode_text(&[3, b'A', 0]).unwrap(), "A");
        assert_eq!(decode_text(&[1, 0xff, 0xfe, 0xe9, 0]).unwrap(), "é");
        assert!(decode_text(&[3, b'A', 0, b'B']).is_err());
        assert!(decode_text(&[3, 0xff]).is_err());
        assert!(syncsafe(&[0xff, 0, 0, 0]).is_err());
    }

    #[test]
    fn apic_fields() {
        let mut frame = vec![0];
        frame.extend_from_slice(b"image/jpeg\0");
        frame.push(3);
        frame.extend_from_slice(b"front\0");
        frame.extend_from_slice(&[0xff, 0xd8, 0xff]);
        let picture = apic(&frame).unwrap();
        assert_eq!(picture.declared.as_deref(), Some("image/jpeg"));
        assert_eq!(picture.data, [0xff, 0xd8, 0xff]);
        // UTF-16 description terminated by a double NUL.
        let mut wide = vec![1];
        wide.extend_from_slice(b"image/png\0");
        wide.push(0);
        wide.extend_from_slice(&[0xff, 0xfe, b'a', 0, 0, 0]);
        wide.extend_from_slice(&[1, 2, 3]);
        assert_eq!(apic(&wide).unwrap().data, [1, 2, 3]);
        assert!(apic(&[0, b'x']).is_err());
    }

    /// MPEG-1 Layer III stereo frame header followed by a Xing/Info frame.
    fn xing_frame(
        index: &[u8; 4],
        flags: u32,
        frames: u32,
        encoder: &[u8; 4],
        delays: u32,
    ) -> Vec<u8> {
        let mut bytes = vec![0xff, 0xfb, 0x90, 0x00];
        bytes.resize(36, 0);
        bytes.extend_from_slice(index);
        bytes.extend_from_slice(&flags.to_be_bytes());
        if flags & 1 != 0 {
            bytes.extend_from_slice(&frames.to_be_bytes());
        }
        bytes.extend_from_slice(encoder);
        bytes.resize(bytes.len() + 17, 0);
        bytes.extend_from_slice(&delays.to_be_bytes()[1..]);
        bytes.resize(417, 0);
        bytes
    }

    fn duration_of(bytes: &[u8]) -> Result<f64> {
        scan(&mut Cursor::new(bytes), bytes.len() as u64, false).map(|layout| {
            match layout.duration {
                Duration::Checked(seconds) | Duration::Exact(seconds) => seconds,
                Duration::Lofty => unreachable!(),
            }
        })
    }

    /// `count` frames of 128 kbit/s MPEG-1 (417 bytes, or 418 with padding).
    fn cbr(count: usize, bitrate_index: u8) -> Vec<u8> {
        let mut bytes = Vec::new();
        for _ in 0..count {
            bytes.extend_from_slice(&[0xff, 0xfb, bitrate_index << 4, 0x00]);
            let length = match BITRATES_MPEG1.get(usize::from(bitrate_index)) {
                Some(bitrate) if *bitrate > 0 => 144 * *bitrate as usize * 1000 / 44_100,
                _ => 417,
            };
            bytes.resize(bytes.len() + length - 4, 0x55);
        }
        bytes
    }

    #[test]
    fn mp3_without_index_needs_a_constant_bitrate_to_the_last_byte() {
        let stream = cbr(40, 9);
        let seconds = duration_of(&stream).unwrap();
        assert!((seconds - stream.len() as f64 * 8.0 / 128_000.0).abs() < 1e-9);
        // One frame at another bitrate: ffmpeg's estimate is not reproduced.
        let mut varying = cbr(10, 9);
        varying.extend(cbr(1, 8));
        varying.extend(cbr(10, 9));
        assert_eq!(duration_of(&varying).unwrap_err().reason, "unsupported");
        // Trailing bytes and a truncated final frame.
        let mut trailing = cbr(20, 9);
        trailing.extend_from_slice(&[0; 7]);
        assert_eq!(duration_of(&trailing).unwrap_err().reason, "unsupported");
        let truncated = &cbr(20, 9)[..20 * 417 - 5];
        assert_eq!(duration_of(truncated).unwrap_err().reason, "unsupported");
        // Free format and a reserved bitrate.
        assert_eq!(duration_of(&cbr(20, 0)).unwrap_err().reason, "unsupported");
        assert_eq!(duration_of(&cbr(20, 15)).unwrap_err().reason, "corrupt");
    }

    #[test]
    fn mp3_vbri_duration_is_the_frame_count() {
        let mut bytes = vec![0xff, 0xfb, 0x90, 0x00];
        bytes.resize(36, 0);
        bytes.extend_from_slice(b"VBRI");
        bytes.extend_from_slice(&1_u16.to_be_bytes());
        bytes.extend_from_slice(&[0; 4]);
        bytes.extend_from_slice(&1000_u32.to_be_bytes());
        bytes.extend_from_slice(&54_u32.to_be_bytes());
        bytes.resize(417, 0);
        let seconds = duration_of(&bytes).unwrap();
        assert!((seconds - 54.0 * 1152.0 / 44_100.0).abs() < 1e-9);
        // Unknown version or no frames.
        let mut version = bytes.clone();
        version[41] = 2;
        assert_eq!(duration_of(&version).unwrap_err().reason, "unsupported");
        let mut empty = bytes.clone();
        empty[50..54].copy_from_slice(&[0; 4]);
        assert_eq!(duration_of(&empty).unwrap_err().reason, "unsupported");
    }

    #[test]
    fn mp3_crc_protected_index_is_not_found_by_the_reference() {
        let mut frame = xing_frame(b"Info", 1, 100, b"LAME", 0);
        frame[1] = 0xfa;
        assert_eq!(duration_of(&frame).unwrap_err().reason, "unsupported");
    }

    #[test]
    fn mp3_duration_follows_the_reference_gapless_rule() {
        // frames * 1152 samples at 44.1 kHz, minus the 12-bit delay and padding of the
        // encoders ffmpeg trusts; the same count untouched for any other encoder.
        let delays = (576 << 12) | 1000;
        let plain = 100.0 * 1152.0 / 44_100.0;
        let trimmed = (100.0 * 1152.0 - 1576.0) / 44_100.0;
        for encoder in [b"LAME", b"Lavf", b"Lavc"] {
            let seconds = duration_of(&xing_frame(b"Xing", 1, 100, encoder, delays)).unwrap();
            assert!((seconds - trimmed).abs() < 1e-9, "{seconds}");
        }
        for encoder in [b"Xing", b"XXXX", b"lame"] {
            let seconds = duration_of(&xing_frame(b"Info", 1, 100, encoder, delays)).unwrap();
            assert!((seconds - plain).abs() < 1e-9, "{seconds}");
        }
    }

    #[test]
    fn mp3_duration_rejects_unreproducible_or_inconsistent_headers() {
        // Without the frame counter ffmpeg estimates from the bitrate: leave it to the oracle.
        assert_eq!(
            duration_of(&xing_frame(b"Xing", 0, 0, b"LAME", 0))
                .unwrap_err()
                .reason,
            "unsupported"
        );
        assert_eq!(
            duration_of(&xing_frame(b"Xing", 1, 0, b"LAME", 0))
                .unwrap_err()
                .reason,
            "unsupported"
        );
        // A trim larger than the whole stream cannot be a valid gapless tag.
        assert_eq!(
            duration_of(&xing_frame(b"Xing", 1, 1, b"LAME", (600 << 12) | 600))
                .unwrap_err()
                .reason,
            "corrupt"
        );
        // Reserved sampling rate.
        let mut reserved = xing_frame(b"Xing", 1, 10, b"LAME", 0);
        reserved[2] |= 0x0c;
        assert_eq!(duration_of(&reserved).unwrap_err().reason, "corrupt");
        // A Xing frame cut before the LAME block is a truncated file, never a guess.
        let short = &xing_frame(b"Xing", 1, 10, b"LAME", 0)[..48];
        assert_eq!(duration_of(short).unwrap_err().reason, "corrupt");
    }
}
