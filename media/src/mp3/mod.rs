use crate::audio::{
    ambiguous, corrupt, cover_error, insert, limit, read_exact, unsupported, Duration, Layout,
    Picture, Result, MAX_METADATA_BYTES, MAX_TEXT_BYTES,
};
use crate::COVER_BYTES;
use std::collections::HashSet;
use std::io::{Read, Seek, SeekFrom};

mod frame;
mod id3;
#[cfg(test)]
mod tests;

use frame::*;
use id3::*;

pub(crate) fn scan<R: Read + Seek>(
    reader: &mut R,
    file_len: u64,
    want_cover: bool,
) -> Result<Layout> {
    if file_len < 16 {
        return Err(corrupt());
    }
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
    if audio[0] != 0xff || audio[1] & 0xe0 != 0xe0 || audio[1] & 6 != 2 {
        return Err(corrupt());
    }
    let first = parse_frame(audio).ok_or_else(|| {
        if audio[2] >> 4 == 0 {
            unsupported()
        } else {
            corrupt()
        }
    })?;
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
