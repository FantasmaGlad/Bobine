//! Ogg Vorbis and Ogg Opus: one logical stream, the standard header packets.
//!
//! The duration is the granule position of the last page over the sample rate, which is
//! what ffprobe reports (including the Opus pre-skip, which ffmpeg does not subtract). That
//! rule holds only when the stream starts at sample zero: ffmpeg shifts the start time
//! otherwise. The first audio page is therefore checked against the sum of the durations of
//! its own packets (Vorbis blocksizes read back from the setup header, Opus table of
//! contents); any other start, several logical streams or a missing end page use the
//! reference. Tags come from the comment header; a cover is a Base64 picture comment.

use crate::audio::{
    corrupt, limit, read_exact, unsupported, Duration, Layout, Result, MAX_METADATA_BYTES,
};
use crate::vorbis::{self, Pictures};
use std::io::{Read, Seek, SeekFrom};

const MAX_PAGE_BYTES: usize = 27 + 255 + 255 * 255;
const NO_GRANULE: u64 = u64::MAX;

struct Page {
    flags: u8,
    granule: u64,
    serial: u32,
    segments: Vec<u8>,
    body: Vec<u8>,
}

/// Parse a page header (27 bytes and the segment table) at the start of `bytes`.
/// Returns the header fields and the length of the whole page, if it fits.
fn header(bytes: &[u8]) -> Option<(u8, u64, u32, usize, usize)> {
    if bytes.len() < 27 || &bytes[..4] != b"OggS" || bytes[4] != 0 {
        return None;
    }
    let segments = usize::from(bytes[26]);
    let table = bytes.get(27..27 + segments)?;
    let body: usize = table.iter().map(|lacing| usize::from(*lacing)).sum();
    let granule = u64::from_le_bytes(bytes[6..14].try_into().ok()?);
    let serial = u32::from_le_bytes(bytes[14..18].try_into().ok()?);
    Some((bytes[5], granule, serial, segments, 27 + segments + body))
}

fn read_page<R: Read>(reader: &mut R) -> Result<Page> {
    let mut head = [0; 27];
    read_exact(reader, &mut head)?;
    let count = usize::from(head[26]);
    let mut segments = vec![0; count];
    read_exact(reader, &mut segments)?;
    let (flags, granule, serial, _, _) =
        header(&[head.as_slice(), segments.as_slice()].concat()).ok_or_else(corrupt)?;
    let size: usize = segments.iter().map(|lacing| usize::from(*lacing)).sum();
    let mut body = vec![0; size];
    read_exact(reader, &mut body)?;
    Ok(Page {
        flags,
        granule,
        serial,
        segments,
        body,
    })
}

/// Packets are reassembled across pages; only complete ones are returned.
#[derive(Default)]
struct Packets {
    partial: Vec<u8>,
}

impl Packets {
    fn feed(&mut self, page: &Page) -> Result<Vec<Vec<u8>>> {
        // A page continues a packet exactly when the previous page left one open.
        if (page.flags & 1 != 0) != !self.partial.is_empty() {
            return Err(corrupt());
        }
        let mut done = Vec::new();
        let mut at = 0;
        for lacing in &page.segments {
            let end = at + usize::from(*lacing);
            self.partial.extend_from_slice(&page.body[at..end]);
            if self.partial.len() > MAX_METADATA_BYTES + 65_536 {
                return Err(limit());
            }
            at = end;
            if *lacing < 255 {
                done.push(std::mem::take(&mut self.partial));
            }
        }
        Ok(done)
    }
}

enum Codec {
    Vorbis { rate: u64, short: u64, long: u64 },
    Opus,
}

fn identify(packet: &[u8]) -> Result<Codec> {
    if packet.starts_with(b"\x01vorbis") {
        if packet.len() != 30 || packet[29] != 1 {
            return Err(unsupported());
        }
        let version = u32::from_le_bytes(packet[7..11].try_into().map_err(|_| corrupt())?);
        let rate = u64::from(u32::from_le_bytes(
            packet[12..16].try_into().map_err(|_| corrupt())?,
        ));
        let (short, long) = (packet[28] & 0x0f, packet[28] >> 4);
        if version != 0
            || packet[11] == 0
            || rate == 0
            || !(6..=13).contains(&short)
            || !(6..=13).contains(&long)
            || short > long
        {
            return Err(unsupported());
        }
        return Ok(Codec::Vorbis {
            rate,
            short: 1 << short,
            long: 1 << long,
        });
    }
    if packet.starts_with(b"OpusHead") {
        // Version 1, one or two channels with the default mapping, nothing after the header.
        if packet.len() != 19 || packet[8] != 1 || !(1..=2).contains(&packet[9]) || packet[18] != 0
        {
            return Err(unsupported());
        }
        return Ok(Codec::Opus);
    }
    Err(unsupported())
}

/// Blockflag of each mode, from the end of the setup header.
///
/// The mode table is the last structure of the setup header: a 6-bit count minus one, then
/// per mode a blockflag bit, 16 zero bits (window), 16 zero bits (transform) and an 8-bit
/// mapping, and finally the framing bit, the last bit set of the packet. ffmpeg finds it by
/// scanning backwards in the same way; the longest run of modes that has the right count in
/// front of it is taken.
fn modes(setup: &[u8]) -> Result<Vec<bool>> {
    if !setup.starts_with(b"\x05vorbis") {
        return Err(unsupported());
    }
    let bit = |index: usize| (setup[index / 8] >> (index % 8)) & 1;
    let value = |start: usize, width: usize| {
        (0..width).fold(0_usize, |acc, offset| {
            acc | usize::from(bit(start + offset)) << offset
        })
    };
    let last = setup
        .iter()
        .rposition(|byte| *byte != 0)
        .ok_or_else(unsupported)?;
    let framing = last * 8 + (7 - setup[last].leading_zeros() as usize);
    let mut found = None;
    for count in 1..=64_usize {
        let Some(start) = framing.checked_sub(41 * count) else {
            break;
        };
        if start < 7 * 8 + 6 {
            break;
        }
        let zero_fields = (0..count).all(|mode| {
            value(start + 41 * mode + 1, 16) == 0 && value(start + 41 * mode + 17, 16) == 0
        });
        if zero_fields && value(start - 6, 6) == count - 1 {
            found = Some((start, count));
        }
    }
    let (start, count) = found.ok_or_else(unsupported)?;
    Ok((0..count).map(|mode| bit(start + 41 * mode) == 1).collect())
}

/// Samples each completed packet of a Vorbis stream contributes, in order.
fn vorbis_total(packets: &[Vec<u8>], modes: &[bool], short: u64, long: u64) -> Result<u64> {
    let mode_bits = usize::BITS - (modes.len() - 1).leading_zeros();
    let mut total = 0;
    let mut previous = 0;
    for packet in packets {
        let first = *packet.first().ok_or_else(unsupported)?;
        if first & 1 != 0 {
            return Err(unsupported());
        }
        let mode = usize::from(first >> 1) & ((1 << mode_bits) - 1);
        let size = if *modes.get(mode).ok_or_else(unsupported)? {
            long
        } else {
            short
        };
        if previous != 0 {
            total += (previous + size) / 4;
        }
        previous = size;
    }
    Ok(total)
}

/// Samples at 48 kHz in an Opus packet, from its table of contents.
fn opus_samples(packet: &[u8]) -> Result<u64> {
    let toc = *packet.first().ok_or_else(unsupported)?;
    let config = usize::from(toc >> 3);
    let frame: u64 = match config {
        0..=11 => [480, 960, 1920, 2880][config % 4],
        12..=15 => [480, 960][config % 2],
        _ => [120, 240, 480, 960][config % 4],
    };
    let frames = match toc & 3 {
        0 => 1,
        1 | 2 => 2,
        _ => {
            let count = u64::from(*packet.get(1).ok_or_else(corrupt)? & 0x3f);
            if count == 0 {
                return Err(corrupt());
            }
            count
        }
    };
    if frame * frames > 5760 {
        return Err(corrupt());
    }
    Ok(frame * frames)
}

/// The last page of the file: the chain of pages in the final window must end at the end.
fn last_page<R: Read + Seek>(reader: &mut R, file_len: u64) -> Result<(u8, u64, u32)> {
    let window = file_len.min(MAX_PAGE_BYTES as u64 + 27);
    reader
        .seek(SeekFrom::Start(file_len - window))
        .map_err(|_| corrupt())?;
    let mut bytes = vec![0; window as usize];
    read_exact(reader, &mut bytes)?;
    let mut candidate = 0;
    while candidate + 4 <= bytes.len() {
        if &bytes[candidate..candidate + 4] != b"OggS" {
            candidate += 1;
            continue;
        }
        let mut at = candidate;
        while let Some((flags, granule, serial, _, length)) = header(&bytes[at..]) {
            if at + length > bytes.len() {
                break;
            }
            at += length;
            if at == bytes.len() {
                return Ok((flags, granule, serial));
            }
        }
        candidate += 1;
    }
    Err(unsupported())
}

pub(crate) fn scan<R: Read + Seek>(
    reader: &mut R,
    file_len: u64,
    want_cover: bool,
) -> Result<Layout> {
    let first = read_page(reader)?;
    // The identification header is alone on the first page, which begins the stream.
    if first.flags != 0x02 {
        return Err(unsupported());
    }
    let mut packets = Packets::default();
    let ident = packets.feed(&first)?;
    let [ident] = ident.as_slice() else {
        return Err(unsupported());
    };
    if !packets.partial.is_empty() {
        return Err(unsupported());
    }
    let codec = identify(ident)?;
    let needed = if matches!(codec, Codec::Vorbis { .. }) {
        3
    } else {
        2
    };
    let serial = first.serial;
    let mut headers = vec![ident.clone()];
    while headers.len() < needed {
        let page = read_page(reader)?;
        if page.serial != serial || page.flags & 0x06 != 0 {
            return Err(unsupported());
        }
        headers.extend(packets.feed(&page)?);
        if headers.len() > needed || (headers.len() == needed && !packets.partial.is_empty()) {
            // Audio must begin on a fresh page.
            return Err(unsupported());
        }
    }
    let mut layout = Layout::default();
    let comment = &headers[1];
    let content = match codec {
        Codec::Vorbis { .. } => {
            if !comment.starts_with(b"\x03vorbis")
                || comment.last() != Some(&1)
                || comment.len() < 8
            {
                return Err(unsupported());
            }
            &comment[7..comment.len() - 1]
        }
        Codec::Opus => {
            if !comment.starts_with(b"OpusTags") {
                return Err(unsupported());
            }
            &comment[8..]
        }
    };
    vorbis::read(content, &mut layout, Pictures::Base64Comment, want_cover)?;

    // First audio page: the stream starts at sample zero when its granule is exactly the
    // length of its own packets.
    let data = read_page(reader)?;
    if data.serial != serial || data.flags & 0x02 != 0 || data.granule == NO_GRANULE {
        return Err(unsupported());
    }
    let completed = packets.feed(&data)?;
    let (rate, expected) = match &codec {
        Codec::Vorbis { rate, short, long } => {
            let table = modes(&headers[2])?;
            (*rate, vorbis_total(&completed, &table, *short, *long)?)
        }
        Codec::Opus => (
            48_000,
            completed.iter().try_fold(0_u64, |total, packet| {
                Ok::<u64, crate::MediaError>(total + opus_samples(packet)?)
            })?,
        ),
    };
    if data.granule != expected {
        return Err(unsupported());
    }
    let (flags, granule, last_serial) = last_page(reader, file_len)?;
    if last_serial != serial
        || flags & 0x04 == 0
        || granule == NO_GRANULE
        || granule < data.granule
        || granule == 0
    {
        return Err(unsupported());
    }
    layout.duration = Duration::Exact(granule as f64 / rate as f64);
    Ok(layout)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn page(flags: u8, granule: u64, serial: u32, packets: &[&[u8]], open: bool) -> Vec<u8> {
        let mut segments = Vec::new();
        let mut body = Vec::new();
        for (index, packet) in packets.iter().enumerate() {
            body.extend_from_slice(packet);
            let mut left = packet.len();
            while left >= 255 {
                segments.push(255);
                left -= 255;
            }
            // A final packet left open keeps a full 255 lacing value.
            if !(open && index == packets.len() - 1) {
                segments.push(left as u8);
            }
        }
        let mut bytes = b"OggS\0".to_vec();
        bytes.push(flags);
        bytes.extend_from_slice(&granule.to_le_bytes());
        bytes.extend_from_slice(&serial.to_le_bytes());
        bytes.extend_from_slice(&[0; 8]);
        bytes.push(segments.len() as u8);
        bytes.extend_from_slice(&segments);
        bytes.extend_from_slice(&body);
        bytes
    }

    fn comments(items: &[&str]) -> Vec<u8> {
        let mut bytes = 3_u32.to_le_bytes().to_vec();
        bytes.extend_from_slice(b"abc");
        bytes.extend_from_slice(&(items.len() as u32).to_le_bytes());
        for item in items {
            bytes.extend_from_slice(&(item.len() as u32).to_le_bytes());
            bytes.extend_from_slice(item.as_bytes());
        }
        bytes
    }

    /// Setup packet whose tail holds two modes: short (blockflag 0) and long (blockflag 1).
    fn setup() -> Vec<u8> {
        let mut bits: Vec<u8> = Vec::new();
        let mut push = |value: usize, width: usize| {
            for offset in 0..width {
                bits.push(((value >> offset) & 1) as u8);
            }
        };
        push(0b1010_0101, 8);
        push(1, 6);
        for flag in [0, 1] {
            push(flag, 1);
            push(0, 16);
            push(0, 16);
            push(0, 8);
        }
        push(1, 1);
        let mut bytes = b"\x05vorbis".to_vec();
        for chunk in bits.chunks(8) {
            bytes.push(
                chunk
                    .iter()
                    .enumerate()
                    .fold(0, |acc, (index, bit)| acc | (bit << index)),
            );
        }
        bytes
    }

    fn ident() -> Vec<u8> {
        let mut bytes = b"\x01vorbis".to_vec();
        bytes.extend_from_slice(&0_u32.to_le_bytes());
        bytes.push(1);
        bytes.extend_from_slice(&44_100_u32.to_le_bytes());
        bytes.extend_from_slice(&[0; 12]);
        bytes.push(0xb8); // blocksizes 256 and 2048
        bytes.push(1);
        bytes
    }

    fn vorbis_comment(items: &[&str]) -> Vec<u8> {
        [b"\x03vorbis".to_vec(), comments(items), vec![1]].concat()
    }

    /// short, long, long, short: 0 + (256+2048)/4 + 2048/2 + (2048+256)/4 samples.
    fn audio() -> Vec<Vec<u8>> {
        vec![vec![0b00, 7], vec![0b10, 7], vec![0b10, 7], vec![0b00, 7]]
    }

    fn vorbis_file(granule_first: u64, granule_last: u64) -> Vec<u8> {
        let packets = audio();
        let refs: Vec<&[u8]> = packets.iter().map(Vec::as_slice).collect();
        [
            page(0x02, 0, 9, &[&ident()], false),
            page(
                0,
                0,
                9,
                &[&vorbis_comment(&["TITLE=Été", "TRACKNUMBER=3"]), &setup()],
                false,
            ),
            page(0, granule_first, 9, &refs[..3], false),
            page(0x04, granule_last, 9, &refs[3..], false),
        ]
        .concat()
    }

    fn scanned(bytes: &[u8]) -> Result<Layout> {
        scan(&mut Cursor::new(bytes), bytes.len() as u64, true)
    }

    #[test]
    fn vorbis_modes_and_durations() {
        assert_eq!(modes(&setup()).unwrap(), vec![false, true]);
        let samples = (256 + 2048) / 4 + 2048 / 2;
        let bytes = vorbis_file(samples, samples + (2048 + 256) / 4);
        let layout = scanned(&bytes).unwrap();
        assert_eq!(layout.tags["title"], "Été");
        assert_eq!(layout.tags["tracknumber"], "3");
        assert_eq!(
            layout.duration,
            Duration::Exact((samples + 576) as f64 / 44_100.0)
        );
    }

    #[test]
    fn a_stream_that_does_not_start_at_zero_is_refused() {
        let samples = (256 + 2048) / 4 + 2048 / 2;
        // The first audio page announces more samples than its packets hold: ffmpeg would
        // report a non-zero start time.
        let shifted = vorbis_file(samples + 1000, samples + 1576);
        assert_eq!(scanned(&shifted).unwrap_err().reason, "unsupported");
    }

    #[test]
    fn missing_end_page_other_serial_and_truncation_are_refused() {
        let samples = (256 + 2048) / 4 + 2048 / 2;
        let good = vorbis_file(samples, samples + 576);
        let mut no_end = good.clone();
        let last = no_end.len() - audio()[3].len() - 28;
        no_end[last + 5] = 0;
        assert_eq!(scanned(&no_end).unwrap_err().reason, "unsupported");
        let mut serial = good.clone();
        let last = good.len() - audio()[3].len() - 28;
        serial[last + 14] = 8;
        assert_eq!(scanned(&serial).unwrap_err().reason, "unsupported");
        assert!(scanned(&good[..good.len() - 3]).is_err());
        assert!(scanned(b"OggS").is_err());
        let mut trailing = good.clone();
        trailing.push(0);
        assert!(scanned(&trailing).is_err());
    }

    #[test]
    fn opus_duration_includes_the_preskip_like_ffmpeg() {
        let mut head = b"OpusHead".to_vec();
        head.extend_from_slice(&[1, 1]);
        head.extend_from_slice(&312_u16.to_le_bytes());
        head.extend_from_slice(&44_100_u32.to_le_bytes());
        head.extend_from_slice(&[0, 0, 0]);
        let tags = [b"OpusTags".to_vec(), comments(&["ARTIST=Moi"])].concat();
        // Two 20 ms CELT frames (config 19 = 0b10011), then one 10 ms frame of the last page.
        let toc = 19_u8 << 3;
        let packets: [&[u8]; 3] = [&[toc, 1, 2], &[toc, 1, 2], &[(18_u8 << 3), 1]];
        let bytes = [
            page(0x02, 0, 5, &[&head], false),
            page(0, 0, 5, &[&tags], false),
            page(0, 1920, 5, &packets[..2], false),
            page(0x04, 1920 + 480, 5, &packets[2..], false),
        ]
        .concat();
        let layout = scanned(&bytes).unwrap();
        assert_eq!(layout.tags["artist"], "Moi");
        assert_eq!(layout.duration, Duration::Exact(2400.0 / 48_000.0));
        // Opus granule that does not match the packets of the first audio page.
        let off = [
            page(0x02, 0, 5, &[&head], false),
            page(0, 0, 5, &[&tags], false),
            page(0, 1000, 5, &packets[..2], false),
            page(0x04, 2400, 5, &packets[2..], false),
        ]
        .concat();
        assert_eq!(scanned(&off).unwrap_err().reason, "unsupported");
    }

    #[test]
    fn opus_table_of_contents() {
        assert_eq!(opus_samples(&[19 << 3]).unwrap(), 960);
        assert_eq!(opus_samples(&[(19 << 3) | 1, 0]).unwrap(), 1920);
        assert_eq!(opus_samples(&[(1 << 3) | 3, 3]).unwrap(), 2880);
        assert_eq!(
            opus_samples(&[(12 << 3) | 3, 0]).unwrap_err().reason,
            "corrupt"
        );
        assert!(opus_samples(&[]).is_err());
        assert!(opus_samples(&[(3 << 3) | 3, 6]).is_err());
    }

    #[test]
    fn headers_must_end_their_page_and_use_one_stream() {
        // Audio data sharing the page of the setup header.
        let packets = audio();
        let bytes = [
            page(0x02, 0, 9, &[&ident()], false),
            page(
                0,
                0,
                9,
                &[&vorbis_comment(&[]), &setup(), &packets[0]],
                false,
            ),
        ]
        .concat();
        assert_eq!(scanned(&bytes).unwrap_err().reason, "unsupported");
        // A second logical stream begins before the headers are complete.
        let two = [
            page(0x02, 0, 9, &[&ident()], false),
            page(0x02, 0, 4, &[&ident()], false),
        ]
        .concat();
        assert_eq!(scanned(&two).unwrap_err().reason, "unsupported");
        // Unknown codec.
        let speex = page(0x02, 0, 9, &[b"Speex   "], false);
        assert_eq!(scanned(&speex).unwrap_err().reason, "unsupported");
    }
}
