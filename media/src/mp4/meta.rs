use super::*;

pub(super) fn text_item(item: &[u8]) -> Result<String> {
    let payload = single_data(item, 1)?;
    if payload.is_empty() || payload.len() > MAX_TEXT_BYTES {
        return Err(unsupported());
    }
    String::from_utf8(payload.to_vec()).map_err(|_| corrupt())
}

pub(super) fn single_data(item: &[u8], kind: u32) -> Result<&[u8]> {
    let list = boxes(item)?;
    let [(name, data)] = list.as_slice() else {
        return Err(unsupported());
    };
    if name != b"data" || data.len() < 8 || be32(data, 0)? != u64::from(kind) {
        return Err(unsupported());
    }
    Ok(&data[8..])
}

pub(super) fn number_item(item: &[u8]) -> Result<String> {
    let payload = single_data(item, 0)?;
    if payload.len() != 8 || payload[..2] != [0, 0] || payload[6..] != [0, 0] {
        return Err(unsupported());
    }
    let current = u16::from_be_bytes([payload[2], payload[3]]);
    let total = u16::from_be_bytes([payload[4], payload[5]]);
    if current > 0x7fff || total > 0x7fff {
        return Err(unsupported());
    }
    Ok(if total == 0 {
        format!("{current}")
    } else {
        format!("{current}/{total}")
    })
}

pub(super) fn read_meta(meta: &[u8], layout: &mut Layout, want_cover: bool) -> Result<()> {
    let body = meta.get(4..).ok_or_else(corrupt)?;
    let (mut handler, mut items) = (None, None);
    for (kind, inner) in boxes(body)? {
        match &kind {
            b"hdlr" => once(&mut handler, inner)?,
            b"ilst" => once(&mut items, inner)?,
            b"free" => {}
            _ => return Err(unsupported()),
        }
    }
    if handler.and_then(|hdlr| hdlr.get(8..12)) != Some(b"mdir") {
        return Err(unsupported());
    }
    for (kind, item) in boxes(items.ok_or_else(corrupt)?)? {
        let key = match &kind {
            b"\xa9nam" => "title",
            b"\xa9ART" => "artist",
            b"\xa9alb" => "album",
            b"aART" => "album_artist",
            b"\xa9day" => "date",
            b"\xa9gen" => "genre",
            b"trkn" => {
                insert(&mut layout.tags, "track", number_item(item)?)?;
                continue;
            }
            b"disk" => {
                insert(&mut layout.tags, "disc", number_item(item)?)?;
                continue;
            }
            b"covr" => {
                for (name, data) in boxes(item)? {
                    if &name != b"data" || data.len() < 8 {
                        return Err(unsupported());
                    }
                    if data.len() - 8 > COVER_BYTES {
                        return Err(limit());
                    }
                    layout.add_picture(want_cover, || {
                        let mime = match be32(data, 0).map_err(cover_error)? {
                            13 => "image/jpeg",
                            14 => "image/png",
                            _ => return Err(cover_error(unsupported())),
                        };
                        Ok(Picture {
                            declared: Some(mime.to_owned()),
                            data: data[8..].to_vec(),
                        })
                    })?;
                }
                continue;
            }
            b"\xa9too" | b"\xa9cmt" | b"\xa9wrt" | b"\xa9grp" | b"\xa9lyr" | b"cprt" | b"desc"
            | b"ldes" | b"cpil" | b"pgap" | b"tmpo" | b"stik" | b"rtng" | b"hdvd" => {
                let list = boxes(item)?;
                if !matches!(list.as_slice(), [(name, _)] if name == b"data") {
                    return Err(unsupported());
                }
                continue;
            }
            _ => return Err(unsupported()),
        };
        insert(&mut layout.tags, key, text_item(item)?)?;
    }
    Ok(())
}
