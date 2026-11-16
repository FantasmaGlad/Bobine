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
    let mut wide = vec![1];
    wide.extend_from_slice(b"image/png\0");
    wide.push(0);
    wide.extend_from_slice(&[0xff, 0xfe, b'a', 0, 0, 0]);
    wide.extend_from_slice(&[1, 2, 3]);
    assert_eq!(apic(&wide).unwrap().data, [1, 2, 3]);
    assert!(apic(&[0, b'x']).is_err());
}

fn xing_frame(index: &[u8; 4], flags: u32, frames: u32, encoder: &[u8; 4], delays: u32) -> Vec<u8> {
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
    scan(&mut Cursor::new(bytes), bytes.len() as u64, false).map(|layout| match layout.duration {
        Duration::Checked(seconds) | Duration::Exact(seconds) => seconds,
        Duration::Lofty => unreachable!(),
    })
}

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
    let mut varying = cbr(10, 9);
    varying.extend(cbr(1, 8));
    varying.extend(cbr(10, 9));
    assert_eq!(duration_of(&varying).unwrap_err().reason, "unsupported");
    let mut trailing = cbr(20, 9);
    trailing.extend_from_slice(&[0; 7]);
    assert_eq!(duration_of(&trailing).unwrap_err().reason, "unsupported");
    let truncated = &cbr(20, 9)[..20 * 417 - 5];
    assert_eq!(duration_of(truncated).unwrap_err().reason, "unsupported");
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
    assert_eq!(
        duration_of(&xing_frame(b"Xing", 1, 1, b"LAME", (600 << 12) | 600))
            .unwrap_err()
            .reason,
        "corrupt"
    );
    let mut reserved = xing_frame(b"Xing", 1, 10, b"LAME", 0);
    reserved[2] |= 0x0c;
    assert_eq!(duration_of(&reserved).unwrap_err().reason, "corrupt");
    let short = &xing_frame(b"Xing", 1, 10, b"LAME", 0)[..48];
    assert_eq!(duration_of(short).unwrap_err().reason, "corrupt");
}
