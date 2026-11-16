use super::*;

pub(super) fn syncsafe(bytes: &[u8]) -> Result<usize> {
    if bytes.len() != 4 || bytes.iter().any(|byte| byte & 0x80 != 0) {
        return Err(corrupt());
    }
    Ok(bytes
        .iter()
        .fold(0, |size, byte| (size << 7) | usize::from(*byte)))
}

pub(super) fn decode_text(bytes: &[u8]) -> Result<String> {
    let (&encoding, bytes) = bytes.split_first().ok_or_else(corrupt)?;
    let text = match encoding {
        0 => bytes.iter().map(|byte| char::from(*byte)).collect(),
        3 => String::from_utf8(bytes.to_vec()).map_err(|_| corrupt())?,
        1 | 2 => {
            let (little, bytes) = if encoding == 1 {
                if bytes.starts_with(&[0xff, 0xfe]) {
                    (true, &bytes[2..])
                } else if bytes.starts_with(&[0xfe, 0xff]) {
                    (false, &bytes[2..])
                } else {
                    return Err(unsupported());
                }
            } else {
                (false, bytes)
            };
            if bytes.len() % 2 != 0 {
                return Err(corrupt());
            }
            let units = bytes.as_chunks::<2>().0.iter().map(|unit| {
                if little {
                    u16::from_le_bytes([unit[0], unit[1]])
                } else {
                    u16::from_be_bytes([unit[0], unit[1]])
                }
            });
            char::decode_utf16(units)
                .collect::<std::result::Result<String, _>>()
                .map_err(|_| corrupt())?
        }
        _ => return Err(unsupported()),
    };
    let text = text.trim_end_matches('\0').to_owned();
    if text.contains('\0') {
        return Err(ambiguous());
    }
    Ok(text)
}

pub(super) fn apic(data: &[u8]) -> Result<Picture> {
    let (&encoding, rest) = data.split_first().ok_or_else(corrupt)?;
    if !matches!(encoding, 0..=3) {
        return Err(unsupported());
    }
    let end = rest
        .iter()
        .position(|byte| *byte == 0)
        .ok_or_else(corrupt)?;
    let mime: String = rest[..end].iter().map(|byte| char::from(*byte)).collect();
    let rest = rest.get(end + 2..).ok_or_else(corrupt)?;
    let wide = matches!(encoding, 1 | 2);
    let mut at = 0;
    loop {
        let step = if wide { 2 } else { 1 };
        let unit = rest.get(at..at + step).ok_or_else(corrupt)?;
        at += step;
        if unit.iter().all(|byte| *byte == 0) {
            break;
        }
    }
    Ok(Picture {
        declared: Some(mime),
        data: rest[at..].to_vec(),
    })
}
