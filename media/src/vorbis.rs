//! Vorbis comments (FLAC, Ogg Vorbis, Opus) and the FLAC picture block.

use crate::audio::{corrupt, cover_error, insert, limit, unsupported, Layout, Picture, Result};
use crate::image;
use crate::COVER_BYTES;

fn take<'a>(content: &mut &'a [u8], size: usize) -> Result<&'a [u8]> {
    if content.len() < size {
        return Err(corrupt());
    }
    let (head, tail) = content.split_at(size);
    *content = tail;
    Ok(head)
}

fn number_le(content: &mut &[u8]) -> Result<usize> {
    Ok(u32::from_le_bytes(take(content, 4)?.try_into().map_err(|_| corrupt())?) as usize)
}

fn number_be(content: &mut &[u8]) -> Result<usize> {
    Ok(u32::from_be_bytes(take(content, 4)?.try_into().map_err(|_| corrupt())?) as usize)
}

/// A FLAC `PICTURE` block body, also the payload of an Ogg `METADATA_BLOCK_PICTURE` comment.
pub(crate) fn flac_picture(block: &[u8]) -> Result<Picture> {
    let mut input = block;
    number_be(&mut input)?;
    let length = number_be(&mut input)?;
    let mime = take(&mut input, length)?;
    let length = number_be(&mut input)?;
    take(&mut input, length)?;
    for _ in 0..4 {
        number_be(&mut input)?;
    }
    let length = number_be(&mut input)?;
    if length > COVER_BYTES {
        return Err(limit());
    }
    let data = take(&mut input, length)?;
    if !input.is_empty() {
        return Err(corrupt());
    }
    Ok(Picture {
        declared: Some(mime.iter().map(|byte| char::from(*byte)).collect()),
        data: data.to_vec(),
    })
}

/// Which pictures a comment block may carry: FLAC has dedicated blocks and rejects the
/// Ogg convention; Ogg Vorbis and Opus carry them as a Base64 comment.
#[derive(Clone, Copy, PartialEq)]
pub(crate) enum Pictures {
    Refuse,
    Base64Comment,
}

/// Read a comment block (vendor string, then `KEY=value` items) into `layout`.
///
/// Keys that ffmpeg could map onto the fields the application reads are stored; a few
/// keys known to be unrelated are skipped; any other key is outside the subset.
pub(crate) fn read(
    content: &[u8],
    layout: &mut Layout,
    pictures: Pictures,
    want_cover: bool,
) -> Result<()> {
    let mut input = content;
    let vendor_len = number_le(&mut input)?;
    take(&mut input, vendor_len)?;
    let count = number_le(&mut input)?;
    if count > 256 {
        return Err(limit());
    }
    for _ in 0..count {
        let length = number_le(&mut input)?;
        let item = std::str::from_utf8(take(&mut input, length)?).map_err(|_| corrupt())?;
        let (key, value) = item.split_once('=').ok_or_else(corrupt)?;
        let key = key.to_ascii_lowercase();
        match key.as_str() {
            "title" | "artist" | "author" | "performer" | "album" | "album_artist"
            | "albumartist" | "band" | "track" | "tracknumber" | "disc" | "discnumber" | "disk"
            | "date" | "year" | "originalyear" | "creation_time" | "genre" => {
                insert(&mut layout.tags, &key, value.to_owned())?
            }
            "encoder" | "comment" | "description" | "copyright" => {}
            "metadata_block_picture" if pictures == Pictures::Base64Comment => {
                layout.add_picture(want_cover, || {
                    let block = image::base64_decode(value.as_bytes())
                        .ok_or_else(|| cover_error(unsupported()))?;
                    flac_picture(&block).map_err(cover_error)
                })?;
            }
            _ => return Err(unsupported()),
        }
    }
    if !input.is_empty() {
        return Err(corrupt());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn block(items: &[&str]) -> Vec<u8> {
        let mut bytes = 5_u32.to_le_bytes().to_vec();
        bytes.extend_from_slice(b"vendo");
        bytes.extend_from_slice(&(items.len() as u32).to_le_bytes());
        for item in items {
            bytes.extend_from_slice(&(item.len() as u32).to_le_bytes());
            bytes.extend_from_slice(item.as_bytes());
        }
        bytes
    }

    #[test]
    fn known_keys_are_stored_unrelated_ones_skipped_unknown_refused() {
        let mut layout = Layout::default();
        read(
            &block(&["TITLE=A", "Artist=B", "ENCODER=x", "COMMENT=y"]),
            &mut layout,
            Pictures::Refuse,
            false,
        )
        .unwrap();
        assert_eq!(layout.tags["title"], "A");
        assert_eq!(layout.tags["artist"], "B");
        assert_eq!(layout.tags.len(), 2);
        let refused = read(
            &block(&["REPLAYGAIN_TRACK_GAIN=1"]),
            &mut Layout::default(),
            Pictures::Refuse,
            false,
        );
        assert_eq!(refused.unwrap_err().reason, "unsupported");
        let twice = read(
            &block(&["TITLE=A", "title=B"]),
            &mut Layout::default(),
            Pictures::Refuse,
            false,
        );
        assert_eq!(twice.unwrap_err().reason, "ambiguous_metadata");
        let extra = [block(&["TITLE=A"]), vec![0]].concat();
        assert_eq!(
            read(&extra, &mut Layout::default(), Pictures::Refuse, false)
                .unwrap_err()
                .reason,
            "corrupt"
        );
    }

    #[test]
    fn picture_comment_is_an_ogg_convention() {
        let mut picture = Vec::new();
        for value in [3_u32, 10] {
            picture.extend_from_slice(&value.to_be_bytes());
        }
        picture.extend_from_slice(b"image/jpeg");
        picture.extend_from_slice(&0_u32.to_be_bytes());
        for _ in 0..4 {
            picture.extend_from_slice(&0_u32.to_be_bytes());
        }
        picture.extend_from_slice(&3_u32.to_be_bytes());
        picture.extend_from_slice(&[0xff, 0xd8, 0xff]);
        let comment = format!("METADATA_BLOCK_PICTURE={}", image::base64_encode(&picture));
        let mut layout = Layout::default();
        read(
            &block(&[&comment]),
            &mut layout,
            Pictures::Base64Comment,
            true,
        )
        .unwrap();
        assert_eq!(layout.pictures, 1);
        assert_eq!(layout.picture.unwrap().data, [0xff, 0xd8, 0xff]);
        let flac = read(
            &block(&[&comment]),
            &mut Layout::default(),
            Pictures::Refuse,
            true,
        );
        assert_eq!(flac.unwrap_err().reason, "unsupported");
        // Counted but not extracted when only the metadata is wanted.
        let mut counted = Layout::default();
        read(
            &block(&[&comment]),
            &mut counted,
            Pictures::Base64Comment,
            false,
        )
        .unwrap();
        assert_eq!((counted.pictures, counted.picture.is_none()), (1, true));
    }
}
