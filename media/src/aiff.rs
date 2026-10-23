//! AIFF: big-endian PCM in a `FORM`/`AIFF` container. Not AIFF-C, not an ID3 chunk.
//!
//! ffmpeg's muxer writes `NAME` (title), `AUTH` (author), `(c) ` and `ANNO`; the duration
//! is the frame count of `COMM` over its sample rate. The sound data length must agree
//! with that count, otherwise the file is not what its header claims.

use crate::audio::{
    ambiguous, corrupt, insert, limit, read_exact, unsupported, Duration, Layout, Result,
    MAX_TEXT_BYTES,
};
use crate::wav::info_text;
use std::io::{Read, Seek, SeekFrom};

/// IEEE 754 80-bit extended precision (the AIFF sample rate) when it is a plain integer rate.
fn extended_rate(bytes: &[u8; 10]) -> Result<u64> {
    let exponent = (u16::from(bytes[0] & 0x7f) << 8) | u16::from(bytes[1]);
    let mantissa = u64::from_be_bytes(bytes[2..10].try_into().map_err(|_| corrupt())?);
    if bytes[0] & 0x80 != 0 || mantissa >> 63 == 0 {
        return Err(unsupported());
    }
    // value = mantissa * 2^(exponent - 16383 - 63)
    let shift = i32::from(exponent) - 16383 - 63;
    let value = if shift >= 0 {
        if shift > 10 {
            return Err(unsupported());
        }
        mantissa.checked_shl(shift as u32).ok_or_else(unsupported)?
    } else {
        let shift = (-shift) as u32;
        if shift >= 64 || mantissa & ((1_u64 << shift) - 1) != 0 {
            return Err(unsupported());
        }
        mantissa >> shift
    };
    if !(1000..=768_000).contains(&value) {
        return Err(unsupported());
    }
    Ok(value)
}

pub(crate) fn scan<R: Read + Seek>(reader: &mut R, file_len: u64) -> Result<Layout> {
    let mut header = [0; 12];
    read_exact(reader, &mut header)?;
    if &header[..4] != b"FORM" || &header[8..12] != b"AIFF" {
        return Err(unsupported());
    }
    let declared = u64::from(u32::from_be_bytes(
        header[4..8].try_into().map_err(|_| corrupt())?,
    )) + 8;
    if declared != file_len {
        return Err(unsupported());
    }
    let mut layout = Layout::default();
    let mut position = 12_u64;
    // (frames, rate, bytes per frame) from COMM; length of the sound data from SSND.
    let mut format: Option<(u64, u64, u64)> = None;
    let mut sound: Option<u64> = None;
    for _ in 0..128 {
        if position == file_len {
            let ((frames, rate, frame_bytes), sound) = match (format, sound) {
                (Some(format), Some(sound)) => (format, sound),
                _ => return Err(corrupt()),
            };
            if frames == 0 {
                return Err(corrupt());
            }
            if frames.checked_mul(frame_bytes) != Some(sound) {
                return Err(ambiguous());
            }
            layout.duration = Duration::Exact(frames as f64 / rate as f64);
            return Ok(layout);
        }
        let mut chunk = [0; 8];
        read_exact(reader, &mut chunk)?;
        let size = u32::from_be_bytes(chunk[4..8].try_into().map_err(|_| corrupt())?) as usize;
        position += 8 + size as u64 + (size % 2) as u64;
        if position > file_len {
            return Err(corrupt());
        }
        match &chunk[..4] {
            b"COMM" => {
                if format.is_some() || size != 18 {
                    return Err(unsupported());
                }
                let mut body = [0; 18];
                read_exact(reader, &mut body)?;
                let channels = u64::from(u16::from_be_bytes([body[0], body[1]]));
                let frames = u64::from(u32::from_be_bytes([body[2], body[3], body[4], body[5]]));
                let bits = u64::from(u16::from_be_bytes([body[6], body[7]]));
                if channels == 0 || channels > 8 || !matches!(bits, 8 | 16 | 24 | 32) {
                    return Err(unsupported());
                }
                let rate = extended_rate(body[8..18].try_into().map_err(|_| corrupt())?)?;
                format = Some((frames, rate, channels * bits / 8));
            }
            b"SSND" => {
                if sound.is_some() || format.is_none() || size < 8 {
                    return Err(unsupported());
                }
                let mut head = [0; 8];
                read_exact(reader, &mut head)?;
                let offset = u64::from(u32::from_be_bytes([head[0], head[1], head[2], head[3]]));
                let data = (size as u64 - 8).checked_sub(offset).ok_or_else(corrupt)?;
                sound = Some(data);
                reader
                    .seek(SeekFrom::Current(size as i64 - 8))
                    .map_err(|_| corrupt())?;
            }
            b"NAME" | b"AUTH" | b"(c) " | b"ANNO" => {
                if size > MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let mut body = vec![0; size];
                read_exact(reader, &mut body)?;
                let text = info_text(&body)?;
                match &chunk[..4] {
                    b"NAME" => insert(&mut layout.tags, "title", text)?,
                    b"AUTH" => insert(&mut layout.tags, "author", text)?,
                    // Copyright and comment are tags the application does not read.
                    _ => {}
                }
            }
            _ => return Err(unsupported()),
        }
        if !size.is_multiple_of(2) {
            reader.seek(SeekFrom::Current(1)).map_err(|_| corrupt())?;
        }
    }
    Err(limit())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    /// 44.1 kHz in 80-bit extended precision.
    const RATE_44100: [u8; 10] = [0x40, 0x0e, 0xac, 0x44, 0, 0, 0, 0, 0, 0];

    fn comm(frames: u32, bits: u16, rate: [u8; 10]) -> Vec<u8> {
        let mut chunk = b"COMM".to_vec();
        chunk.extend_from_slice(&18_u32.to_be_bytes());
        chunk.extend_from_slice(&1_u16.to_be_bytes());
        chunk.extend_from_slice(&frames.to_be_bytes());
        chunk.extend_from_slice(&bits.to_be_bytes());
        chunk.extend_from_slice(&rate);
        chunk
    }

    fn ssnd(bytes: usize) -> Vec<u8> {
        let mut chunk = b"SSND".to_vec();
        chunk.extend_from_slice(&((bytes + 8) as u32).to_be_bytes());
        chunk.extend_from_slice(&[0; 8]);
        chunk.resize(chunk.len() + bytes, 1);
        chunk
    }

    fn text(id: &[u8; 4], value: &[u8]) -> Vec<u8> {
        let mut chunk = id.to_vec();
        chunk.extend_from_slice(&(value.len() as u32).to_be_bytes());
        chunk.extend_from_slice(value);
        if value.len() % 2 == 1 {
            chunk.push(0);
        }
        chunk
    }

    fn form(chunks: &[Vec<u8>]) -> Vec<u8> {
        let body: Vec<u8> = chunks.concat();
        let mut bytes = b"FORM".to_vec();
        bytes.extend_from_slice(&((body.len() + 4) as u32).to_be_bytes());
        bytes.extend_from_slice(b"AIFF");
        bytes.extend_from_slice(&body);
        bytes
    }

    fn scanned(bytes: &[u8]) -> Result<Layout> {
        scan(&mut Cursor::new(bytes), bytes.len() as u64)
    }

    #[test]
    fn extended_precision_rates() {
        assert_eq!(extended_rate(&RATE_44100).unwrap(), 44_100);
        // 8 kHz, 48 kHz.
        assert_eq!(
            extended_rate(&[0x40, 0x0b, 0xfa, 0, 0, 0, 0, 0, 0, 0]).unwrap(),
            8000
        );
        assert_eq!(
            extended_rate(&[0x40, 0x0e, 0xbb, 0x80, 0, 0, 0, 0, 0, 0]).unwrap(),
            48_000
        );
        // Not normalized, negative, fractional.
        assert!(extended_rate(&[0x40, 0x0e, 0x2c, 0x44, 0, 0, 0, 0, 0, 0]).is_err());
        assert!(extended_rate(&[0xc0, 0x0e, 0xac, 0x44, 0, 0, 0, 0, 0, 0]).is_err());
        assert!(extended_rate(&[0x40, 0x0e, 0xac, 0x44, 0, 0, 0, 0, 0, 1]).is_err());
    }

    #[test]
    fn duration_is_frames_over_rate_and_title_comes_from_name() {
        let bytes = form(&[
            text(b"NAME", "Été\0".as_bytes()),
            comm(44_100, 16, RATE_44100),
            ssnd(88_200),
        ]);
        let layout = scanned(&bytes).unwrap();
        assert_eq!(layout.tags["title"], "Été");
        assert_eq!(layout.duration, Duration::Exact(1.0));
        let author = form(&[
            text(b"AUTH", b"Moi"),
            text(b"ANNO", b"x\0"),
            comm(10, 16, RATE_44100),
            ssnd(20),
        ]);
        assert_eq!(scanned(&author).unwrap().tags["author"], "Moi");
    }

    #[test]
    fn inconsistent_or_unknown_layouts_are_refused() {
        // Sound data shorter than the frame count claims.
        let short = form(&[comm(100, 16, RATE_44100), ssnd(100)]);
        assert_eq!(scanned(&short).unwrap_err().reason, "ambiguous_metadata");
        // Unknown chunk (ID3, markers, application data), AIFF-C, missing parts, bad length.
        let id3 = form(&[comm(10, 16, RATE_44100), text(b"ID3 ", b"abcd"), ssnd(20)]);
        assert_eq!(scanned(&id3).unwrap_err().reason, "unsupported");
        let mut aifc = form(&[comm(10, 16, RATE_44100), ssnd(20)]);
        aifc[11] = b'C';
        assert_eq!(scanned(&aifc).unwrap_err().reason, "unsupported");
        assert_eq!(
            scanned(&form(&[comm(10, 16, RATE_44100)]))
                .unwrap_err()
                .reason,
            "corrupt"
        );
        assert_eq!(
            scanned(&form(&[ssnd(20), comm(10, 16, RATE_44100)]))
                .unwrap_err()
                .reason,
            "unsupported"
        );
        let mut long = form(&[comm(10, 16, RATE_44100), ssnd(20)]);
        long.push(0);
        assert_eq!(scanned(&long).unwrap_err().reason, "unsupported");
        assert_eq!(
            scanned(&form(&[comm(10, 12, RATE_44100), ssnd(20)]))
                .unwrap_err()
                .reason,
            "unsupported"
        );
    }
}
