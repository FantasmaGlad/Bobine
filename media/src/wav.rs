//! WAV: little-endian RIFF PCM with one `fmt ` and one `data` chunk, an optional
//! `LIST`/`INFO` chunk and padding. The duration is Lofty's, which equals ffprobe's for PCM.

use crate::audio::{
    ambiguous, corrupt, insert, limit, read_exact, unsupported, Layout, Result, MAX_TEXT_BYTES,
};
use std::io::{Read, Seek, SeekFrom};

/// ffmpeg's RIFF INFO conversion table: the identifiers it renames to the tags the
/// application reads (`Some`) or to tags it does not read (`None`). Any other identifier
/// would keep its raw four-letter name, which could collide with a field name.
fn info_key(id: &[u8]) -> Option<Option<&'static str>> {
    Some(match id {
        b"INAM" => Some("title"),
        b"IART" => Some("artist"),
        b"IPRD" => Some("album"),
        b"ICRD" => Some("date"),
        b"IGNR" => Some("genre"),
        b"IPRT" => Some("track"),
        b"ISFT" | b"ICMT" | b"ICOP" | b"ILNG" | b"ITCH" | b"ISMP" => None,
        _ => return Option::None,
    })
}

/// The text of one INFO (or AIFF text) item: UTF-8 up to the first NUL, with only NULs after it.
pub(crate) fn info_text(value: &[u8]) -> Result<String> {
    let end = value
        .iter()
        .position(|byte| *byte == 0)
        .unwrap_or(value.len());
    if value[end..].iter().any(|byte| *byte != 0) || end == 0 {
        return Err(unsupported());
    }
    String::from_utf8(value[..end].to_vec()).map_err(|_| corrupt())
}

fn read_info(content: &[u8], layout: &mut Layout) -> Result<()> {
    if content.len() < 4 || &content[..4] != b"INFO" {
        return Err(unsupported());
    }
    let mut cursor = 4;
    while cursor < content.len() {
        let head = content.get(cursor..cursor + 8).ok_or_else(corrupt)?;
        let size = u32::from_le_bytes(head[4..8].try_into().map_err(|_| corrupt())?) as usize;
        let end = (cursor + 8)
            .checked_add(size)
            .filter(|end| *end <= content.len())
            .ok_or_else(corrupt)?;
        if size > MAX_TEXT_BYTES {
            return Err(limit());
        }
        let key = info_key(&head[..4]).ok_or_else(unsupported)?;
        let text = info_text(&content[cursor + 8..end])?;
        if let Some(key) = key {
            insert(&mut layout.tags, key, text)?;
        }
        cursor = end + size % 2;
    }
    Ok(())
}

pub(crate) fn scan<R: Read + Seek>(reader: &mut R, file_len: u64) -> Result<Layout> {
    let mut header = [0; 12];
    read_exact(reader, &mut header)?;
    if &header[..4] != b"RIFF" || &header[8..12] != b"WAVE" {
        return Err(unsupported());
    }
    let declared = u64::from(u32::from_le_bytes(
        header[4..8].try_into().map_err(|_| corrupt())?,
    )) + 8;
    if declared != file_len {
        return Err(unsupported());
    }
    let mut layout = Layout::default();
    let mut position = 12;
    let mut format_seen = false;
    let mut data_seen = false;
    let mut list_seen = false;
    let mut metadata_bytes = 0;
    for _ in 0..128 {
        if position == file_len {
            return if format_seen && data_seen {
                Ok(layout)
            } else {
                Err(corrupt())
            };
        }
        let mut chunk = [0; 8];
        read_exact(reader, &mut chunk)?;
        let size = u32::from_le_bytes(chunk[4..8].try_into().map_err(|_| corrupt())?) as usize;
        position += 8 + size as u64 + (size % 2) as u64;
        if position > file_len {
            return Err(corrupt());
        }
        match &chunk[..4] {
            b"fmt " => {
                if format_seen || !matches!(size, 16 | 18) {
                    return Err(unsupported());
                }
                format_seen = true;
                let mut format = vec![0; size];
                read_exact(reader, &mut format)?;
                if format[..2] != [1, 0] {
                    return Err(unsupported());
                }
                if size == 18 && format[16..18] != [0, 0] {
                    return Err(unsupported());
                }
            }
            b"data" => {
                if data_seen || !format_seen || size == 0 {
                    return Err(corrupt());
                }
                data_seen = true;
                reader
                    .seek(SeekFrom::Current(size as i64))
                    .map_err(|_| corrupt())?;
            }
            b"LIST" => {
                if list_seen {
                    return Err(ambiguous());
                }
                list_seen = true;
                metadata_bytes += size;
                if metadata_bytes > MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let mut content = vec![0; size];
                read_exact(reader, &mut content)?;
                read_info(&content, &mut layout)?;
            }
            b"JUNK" | b"PAD " => {
                reader
                    .seek(SeekFrom::Current(size as i64))
                    .map_err(|_| corrupt())?;
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

    fn pcm(extra: &[u8]) -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(b"RIFF");
        bytes.extend_from_slice(&((36 + 8000 + extra.len()) as u32).to_le_bytes());
        bytes.extend_from_slice(b"WAVEfmt ");
        bytes.extend_from_slice(&16_u32.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&8000_u32.to_le_bytes());
        bytes.extend_from_slice(&8000_u32.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&8_u16.to_le_bytes());
        bytes.extend_from_slice(extra);
        bytes.extend_from_slice(b"data");
        bytes.extend_from_slice(&8000_u32.to_le_bytes());
        bytes.resize(bytes.len() + 8000, 128);
        bytes
    }

    fn list(items: &[(&[u8; 4], &[u8])]) -> Vec<u8> {
        let mut body = b"INFO".to_vec();
        for (id, value) in items {
            body.extend_from_slice(*id);
            body.extend_from_slice(&(value.len() as u32).to_le_bytes());
            body.extend_from_slice(value);
            if value.len() % 2 == 1 {
                body.push(0);
            }
        }
        let mut chunk = b"LIST".to_vec();
        chunk.extend_from_slice(&(body.len() as u32).to_le_bytes());
        chunk.extend_from_slice(&body);
        chunk
    }

    fn scanned(bytes: &[u8]) -> Result<Layout> {
        scan(&mut Cursor::new(bytes), bytes.len() as u64)
    }

    #[test]
    fn layout_accepts_pcm_rejects_truncation_and_disguised_input() {
        let bytes = pcm(&[]);
        assert!(scanned(&bytes).is_ok());
        assert!(scan(&mut Cursor::new(&bytes[..50]), 50).is_err());
        let mut invalid = bytes.clone();
        invalid[20] = 3;
        assert!(scanned(&invalid).is_err());
    }

    #[test]
    fn info_items_follow_ffmpeg_names() {
        let extra = list(&[
            (b"IART", b"Artiste\0"),
            (b"INAM", "Été\0".as_bytes()),
            (b"ICRD", b"1995\0"),
            (b"IPRT", b"6/14\0"),
            (b"ISFT", b"Lavf\0"),
            (b"IGNR", b"Pop\0"),
            (b"IPRD", b"Disque\0"),
        ]);
        let layout = scanned(&pcm(&extra)).unwrap();
        assert_eq!(layout.tags["title"], "Été");
        assert_eq!(layout.tags["artist"], "Artiste");
        assert_eq!(layout.tags["date"], "1995");
        assert_eq!(layout.tags["track"], "6/14");
        assert_eq!(layout.tags["genre"], "Pop");
        assert_eq!(layout.tags["album"], "Disque");
        assert_eq!(layout.tags.len(), 6);
    }

    #[test]
    fn info_items_outside_the_table_or_irregular_are_refused() {
        // A raw four-letter name that could collide with a field name, or one ffmpeg keeps raw.
        for item in [
            (b"DATE", b"1995\0".as_slice()),
            (b"ITRK", b"3\0"),
            (b"IKEY", b"a\0"),
        ] {
            let extra = list(&[(item.0, item.1)]);
            assert_eq!(scanned(&pcm(&extra)).unwrap_err().reason, "unsupported");
        }
        // Text after the terminator, empty text, invalid UTF-8, duplicates, a second list.
        assert_eq!(
            scanned(&pcm(&list(&[(b"INAM", b"A\0B\0")])))
                .unwrap_err()
                .reason,
            "unsupported"
        );
        assert_eq!(
            scanned(&pcm(&list(&[(b"INAM", b"\0\0")])))
                .unwrap_err()
                .reason,
            "unsupported"
        );
        assert_eq!(
            scanned(&pcm(&list(&[(b"INAM", b"\xff\0")])))
                .unwrap_err()
                .reason,
            "corrupt"
        );
        assert_eq!(
            scanned(&pcm(&list(&[(b"INAM", b"A\0"), (b"INAM", b"B\0")])))
                .unwrap_err()
                .reason,
            "ambiguous_metadata"
        );
        let twice = [list(&[(b"INAM", b"A\0")]), list(&[(b"IART", b"B\0")])].concat();
        assert_eq!(
            scanned(&pcm(&twice)).unwrap_err().reason,
            "ambiguous_metadata"
        );
    }
}
