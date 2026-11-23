use super::*;
use std::io::Cursor;

const BLOCKSIZES_256_AND_2048: u8 = 0xb8;

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
    bytes.push(BLOCKSIZES_256_AND_2048);
    bytes.push(1);
    bytes
}

fn vorbis_comment(items: &[&str]) -> Vec<u8> {
    [b"\x03vorbis".to_vec(), comments(items), vec![1]].concat()
}

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
    let two = [
        page(0x02, 0, 9, &[&ident()], false),
        page(0x02, 0, 4, &[&ident()], false),
    ]
    .concat();
    assert_eq!(scanned(&two).unwrap_err().reason, "unsupported");
    let speex = page(0x02, 0, 9, &[b"Speex   "], false);
    assert_eq!(scanned(&speex).unwrap_err().reason, "unsupported");
}
