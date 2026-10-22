//! Structural checks for an embedded cover image, and the transport encoding.
//!
//! The component never decodes an image. It only hands the raw bytes to the caller when
//! the picture belongs to the families whose reference result (ffmpeg re-encoding to
//! JPEG, then Pillow) was measured to be equivalent to Pillow reading the raw bytes
//! directly (see media/README.md, "Equivalence of covers"). Everything else keeps the
//! reference pipeline: `ambiguous_cover`.

use crate::audio::Result;
use crate::MediaError;

/// Larger bitmaps cost more memory to decode than the reference pipeline is known to bear.
const MAX_PIXELS: u64 = 40_000_000;

fn refuse() -> MediaError {
    MediaError::new(
        "ambiguous_cover",
        "Embedded images require the reference image pipeline",
    )
}

/// MIME type of a picture whose structure is inside the accepted families.
///
/// `declared` is the type announced by the container, when it announces one. A
/// declaration that disagrees with the bytes makes ffmpeg choose the wrong decoder, so the
/// outcome of the reference pipeline cannot be predicted: refuse.
pub(crate) fn classify(data: &[u8], declared: Option<&str>) -> Result<&'static str> {
    let mime = if data.starts_with(&[0xff, 0xd8, 0xff]) {
        jpeg(data)?;
        "image/jpeg"
    } else if data.starts_with(b"\x89PNG\r\n\x1a\n") {
        png(data)?;
        "image/png"
    } else {
        return Err(refuse());
    };
    if let Some(declared) = declared {
        let declared = declared.trim().to_ascii_lowercase();
        let matches = match mime {
            "image/jpeg" => declared == "image/jpeg" || declared == "image/jpg",
            _ => declared == "image/png",
        };
        if !matches {
            return Err(refuse());
        }
    }
    Ok(mime)
}

fn pixels(width: u32, height: u32) -> Result<()> {
    if width == 0 || height == 0 || u64::from(width) * u64::from(height) > MAX_PIXELS {
        return Err(refuse());
    }
    Ok(())
}

/// Baseline, extended-sequential or progressive 8-bit JPEG with one or three components,
/// upright and without an Adobe transform marker.
fn jpeg(data: &[u8]) -> Result<()> {
    let mut position = 2;
    let mut frame = false;
    loop {
        // Fill bytes (0xff) may precede a marker.
        if data.get(position) != Some(&0xff) {
            return Err(refuse());
        }
        while data.get(position + 1) == Some(&0xff) {
            position += 1;
        }
        let marker = *data.get(position + 1).ok_or_else(refuse)?;
        let length = match data.get(position + 2..position + 4) {
            Some(bytes) => usize::from(u16::from_be_bytes([bytes[0], bytes[1]])),
            None => return Err(refuse()),
        };
        if length < 2 {
            return Err(refuse());
        }
        let segment = data
            .get(position + 4..position + 2 + length)
            .ok_or_else(refuse)?;
        match marker {
            0xc0..=0xc2 => {
                if frame || segment.len() < 6 {
                    return Err(refuse());
                }
                let components = segment[5];
                if segment[0] != 8
                    || !matches!(components, 1 | 3)
                    || segment.len() != 6 + 3 * usize::from(components)
                {
                    return Err(refuse());
                }
                let height = u32::from(u16::from_be_bytes([segment[1], segment[2]]));
                let width = u32::from(u16::from_be_bytes([segment[3], segment[4]]));
                pixels(width, height)?;
                frame = true;
            }
            // Lossless, hierarchical, arithmetic coding or a restart outside a scan.
            0xc3 | 0xc5..=0xc7 | 0xc9..=0xcb | 0xcd..=0xcf => return Err(refuse()),
            0xe1 if segment.starts_with(b"Exif\0\0") => exif_upright(&segment[6..])?,
            0xee if segment.starts_with(b"Adobe") => return Err(refuse()),
            0xda => return if frame { Ok(()) } else { Err(refuse()) },
            0xd9 => return Err(refuse()),
            _ => {}
        }
        position += 2 + length;
    }
}

/// ffmpeg applies the EXIF orientation of an attached picture, Pillow's `open` does not:
/// only an absent or neutral orientation gives the same picture.
fn exif_upright(tiff: &[u8]) -> Result<()> {
    let little = match tiff.get(..4) {
        Some(b"II*\0") => true,
        Some(b"MM\0*") => false,
        _ => return Err(refuse()),
    };
    let read16 = |at: usize| -> Result<u16> {
        let bytes = tiff.get(at..at + 2).ok_or_else(refuse)?;
        Ok(if little {
            u16::from_le_bytes([bytes[0], bytes[1]])
        } else {
            u16::from_be_bytes([bytes[0], bytes[1]])
        })
    };
    let read32 = |at: usize| -> Result<u32> {
        let bytes = tiff.get(at..at + 4).ok_or_else(refuse)?;
        let array = [bytes[0], bytes[1], bytes[2], bytes[3]];
        Ok(if little {
            u32::from_le_bytes(array)
        } else {
            u32::from_be_bytes(array)
        })
    };
    let ifd = read32(4)? as usize;
    let count = usize::from(read16(ifd)?);
    for index in 0..count {
        let entry = ifd + 2 + index * 12;
        if read16(entry)? == 0x0112 {
            // Type SHORT, one value, stored inline.
            if read16(entry + 2)? != 3 || read32(entry + 4)? != 1 || read16(entry + 8)? != 1 {
                return Err(refuse());
            }
        }
    }
    Ok(())
}

/// Non-interlaced 8-bit PNG (grey, RGB, palette, grey+alpha, RGBA) without animation or EXIF.
fn png(data: &[u8]) -> Result<()> {
    let mut position = 8;
    let mut header = false;
    let mut palette_needed = false;
    let mut palette = false;
    let mut image_data = false;
    loop {
        let head = data.get(position..position + 8).ok_or_else(refuse)?;
        let length = u32::from_be_bytes([head[0], head[1], head[2], head[3]]) as usize;
        let kind = &head[4..8];
        let body = data
            .get(position + 8..position + 8 + length)
            .ok_or_else(refuse)?;
        // The CRC is not verified here: both decoders do, and a failure is a fallback.
        if data
            .get(position + 8 + length..position + 12 + length)
            .is_none()
        {
            return Err(refuse());
        }
        match kind {
            b"IHDR" => {
                if header || length != 13 {
                    return Err(refuse());
                }
                header = true;
                let width = u32::from_be_bytes([body[0], body[1], body[2], body[3]]);
                let height = u32::from_be_bytes([body[4], body[5], body[6], body[7]]);
                pixels(width, height)?;
                let (depth, color, compression, filter, interlace) =
                    (body[8], body[9], body[10], body[11], body[12]);
                if depth != 8
                    || !matches!(color, 0 | 2 | 3 | 4 | 6)
                    || compression != 0
                    || filter != 0
                    || interlace != 0
                {
                    return Err(refuse());
                }
                palette_needed = color == 3;
            }
            _ if !header => return Err(refuse()),
            b"PLTE" => palette = true,
            b"IDAT" => image_data = true,
            b"IEND" => {
                return if image_data && (palette || !palette_needed) {
                    Ok(())
                } else {
                    Err(refuse())
                }
            }
            b"acTL" | b"eXIf" | b"fdAT" => return Err(refuse()),
            // An unknown critical chunk is not understood by the reference either.
            other if other[0].is_ascii_uppercase() => return Err(refuse()),
            _ => {}
        }
        position += 12 + length;
    }
}

const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// Standard padded Base64 (RFC 4648).
pub(crate) fn base64_encode(data: &[u8]) -> String {
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for chunk in data.chunks(3) {
        let triple = (u32::from(chunk[0]) << 16)
            | (u32::from(*chunk.get(1).unwrap_or(&0)) << 8)
            | u32::from(*chunk.get(2).unwrap_or(&0));
        out.push(char::from(ALPHABET[(triple >> 18) as usize & 63]));
        out.push(char::from(ALPHABET[(triple >> 12) as usize & 63]));
        out.push(if chunk.len() > 1 {
            char::from(ALPHABET[(triple >> 6) as usize & 63])
        } else {
            '='
        });
        out.push(if chunk.len() > 2 {
            char::from(ALPHABET[triple as usize & 63])
        } else {
            '='
        });
    }
    out
}

/// Strict decoder for the Base64 an Ogg comment carries; `None` on any irregularity.
pub(crate) fn base64_decode(text: &[u8]) -> Option<Vec<u8>> {
    if text.is_empty() || !text.len().is_multiple_of(4) {
        return None;
    }
    let mut out = Vec::with_capacity(text.len() / 4 * 3);
    let last = text.len() / 4 - 1;
    for (index, quad) in text.chunks(4).enumerate() {
        let padding = quad.iter().rev().take_while(|byte| **byte == b'=').count();
        if padding > 2 || (padding > 0 && index != last) {
            return None;
        }
        let mut triple = 0_u32;
        for (slot, byte) in quad.iter().enumerate() {
            let value = if slot >= 4 - padding {
                0
            } else {
                ALPHABET.iter().position(|candidate| candidate == byte)? as u32
            };
            triple = (triple << 6) | value;
        }
        let bytes = [(triple >> 16) as u8, (triple >> 8) as u8, triple as u8];
        out.extend_from_slice(&bytes[..3 - padding]);
        // Non-canonical trailing bits would not round-trip.
        if padding > 0 && triple & ((1 << (8 * padding)) - 1) != 0 {
            return None;
        }
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tiny_jpeg(precision: u8, components: u8) -> Vec<u8> {
        let mut bytes = vec![0xff, 0xd8, 0xff, 0xe0, 0, 16];
        bytes.extend_from_slice(b"JFIF\0\x01\x01\0\0\x01\0\x01\0\0");
        bytes.extend_from_slice(&[
            0xff,
            0xc0,
            0,
            8 + 3 * components,
            precision,
            0,
            4,
            0,
            4,
            components,
        ]);
        for index in 0..components {
            bytes.extend_from_slice(&[index + 1, 0x11, 0]);
        }
        bytes.extend_from_slice(&[0xff, 0xda, 0, 2, 0xff, 0xd9]);
        bytes
    }

    #[test]
    fn jpeg_families() {
        assert_eq!(
            classify(&tiny_jpeg(8, 3), Some("image/jpg")).unwrap(),
            "image/jpeg"
        );
        assert_eq!(classify(&tiny_jpeg(8, 1), None).unwrap(), "image/jpeg");
        assert!(classify(&tiny_jpeg(12, 3), None).is_err());
        assert!(classify(&tiny_jpeg(8, 4), None).is_err());
        // The declared type must agree with the bytes.
        assert!(classify(&tiny_jpeg(8, 3), Some("image/png")).is_err());
        assert!(classify(&tiny_jpeg(8, 3), Some("-->")).is_err());
        // Truncated before the scan.
        let jpeg = tiny_jpeg(8, 3);
        assert!(classify(&jpeg[..20], None).is_err());
    }

    #[test]
    fn jpeg_exif_orientation_must_be_neutral() {
        let exif = |orientation: u16| {
            let mut tiff = b"II*\0\x08\0\0\0\x01\0".to_vec();
            tiff.extend_from_slice(&[0x12, 0x01, 3, 0, 1, 0, 0, 0]);
            tiff.extend_from_slice(&orientation.to_le_bytes());
            tiff.extend_from_slice(&[0, 0, 0, 0, 0, 0]);
            let mut segment = b"Exif\0\0".to_vec();
            segment.extend_from_slice(&tiff);
            let mut bytes = vec![0xff, 0xd8, 0xff, 0xe1];
            bytes.extend_from_slice(&((segment.len() + 2) as u16).to_be_bytes());
            bytes.extend_from_slice(&segment);
            bytes.extend_from_slice(&tiny_jpeg(8, 3)[2..]);
            bytes
        };
        assert!(classify(&exif(1), None).is_ok());
        assert!(classify(&exif(6), None).is_err());
    }

    fn chunk(kind: &[u8; 4], body: &[u8]) -> Vec<u8> {
        let mut bytes = (body.len() as u32).to_be_bytes().to_vec();
        bytes.extend_from_slice(kind);
        bytes.extend_from_slice(body);
        bytes.extend_from_slice(&[0; 4]);
        bytes
    }

    fn tiny_png(depth: u8, color: u8, interlace: u8) -> Vec<u8> {
        let mut header = Vec::new();
        header.extend_from_slice(&4_u32.to_be_bytes());
        header.extend_from_slice(&4_u32.to_be_bytes());
        header.extend_from_slice(&[depth, color, 0, 0, interlace]);
        let mut bytes = b"\x89PNG\r\n\x1a\n".to_vec();
        bytes.extend(chunk(b"IHDR", &header));
        if color == 3 {
            bytes.extend(chunk(b"PLTE", &[0; 3]));
        }
        bytes.extend(chunk(b"IDAT", &[0]));
        bytes.extend(chunk(b"IEND", &[]));
        bytes
    }

    #[test]
    fn png_families() {
        for color in [0, 2, 3, 4, 6] {
            assert_eq!(
                classify(&tiny_png(8, color, 0), Some("image/png")).unwrap(),
                "image/png"
            );
        }
        assert!(classify(&tiny_png(16, 2, 0), None).is_err());
        assert!(classify(&tiny_png(8, 2, 1), None).is_err());
        assert!(classify(&tiny_png(8, 1, 0), None).is_err());
        assert!(classify(&tiny_png(8, 2, 0), Some("image/jpeg")).is_err());
        let mut animated = tiny_png(8, 2, 0);
        animated.splice(33..33, chunk(b"acTL", &[0; 8]));
        assert!(classify(&animated, None).is_err());
        assert!(classify(b"GIF89a", None).is_err());
    }

    #[test]
    fn base64_round_trips_and_rejects_irregular_input() {
        for length in 0..40_usize {
            let data: Vec<u8> = (0..length).map(|index| (index * 37 + 11) as u8).collect();
            let encoded = base64_encode(&data);
            assert_eq!(encoded.len(), length.div_ceil(3) * 4);
            if length > 0 {
                assert_eq!(base64_decode(encoded.as_bytes()).unwrap(), data);
            }
        }
        assert_eq!(base64_encode(b"Man"), "TWFu");
        assert_eq!(base64_encode(b"Ma"), "TWE=");
        for bad in ["", "TWF", "TW=u", "TWE=TWE=", "TW*u", "TWF=", "TR=="] {
            assert!(base64_decode(bad.as_bytes()).is_none(), "{bad}");
        }
    }
}
