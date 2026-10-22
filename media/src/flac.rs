//! FLAC: STREAMINFO, optional padding and seek table, one Vorbis comment block, pictures.

use crate::audio::{
    ambiguous, corrupt, cover_error, limit, read_exact, unsupported, Layout, Result,
    MAX_METADATA_BYTES, MAX_TEXT_BYTES,
};
use crate::vorbis::{self, Pictures};
use crate::COVER_BYTES;
use std::io::{Read, Seek, SeekFrom};

pub(crate) fn scan<R: Read + Seek>(
    reader: &mut R,
    file_len: u64,
    want_cover: bool,
) -> Result<Layout> {
    let mut magic = [0; 4];
    read_exact(reader, &mut magic)?;
    if &magic != b"fLaC" {
        return Err(unsupported());
    }
    let mut layout = Layout::default();
    let mut position = 4_u64;
    let mut total = 0_usize;
    let mut comments_seen = false;
    for block_index in 0..128 {
        let mut header = [0; 4];
        read_exact(reader, &mut header)?;
        let kind = header[0] & 0x7f;
        let size =
            (usize::from(header[1]) << 16) | (usize::from(header[2]) << 8) | usize::from(header[3]);
        position += 4 + size as u64;
        total += size;
        if position > file_len {
            return Err(corrupt());
        }
        if total > MAX_METADATA_BYTES {
            return Err(limit());
        }
        if block_index == 0 && (kind != 0 || size != 34) {
            return Err(corrupt());
        }
        let skip = |reader: &mut R| {
            reader
                .seek(SeekFrom::Current(size as i64))
                .map(|_| ())
                .map_err(|_| corrupt())
        };
        match kind {
            0 if block_index == 0 => skip(reader)?,
            1 | 3 => skip(reader)?,
            4 => {
                if comments_seen {
                    return Err(ambiguous());
                }
                comments_seen = true;
                if size > MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let mut content = vec![0; size];
                read_exact(reader, &mut content)?;
                vorbis::read(&content, &mut layout, Pictures::Refuse, false)?;
            }
            6 => {
                if size > COVER_BYTES + MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let mut read = false;
                layout.add_picture(want_cover, || {
                    read = true;
                    let mut content = vec![0; size];
                    read_exact(reader, &mut content).map_err(cover_error)?;
                    vorbis::flac_picture(&content).map_err(cover_error)
                })?;
                if !read {
                    skip(reader)?;
                }
            }
            _ => return Err(unsupported()),
        }
        if header[0] & 0x80 != 0 {
            if position >= file_len {
                return Err(corrupt());
            }
            return Ok(layout);
        }
    }
    Err(limit())
}
