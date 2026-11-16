use super::*;

pub(super) type Boxes<'a> = Vec<([u8; 4], &'a [u8])>;

pub(super) fn boxes(data: &[u8]) -> Result<Boxes<'_>> {
    let mut out = Vec::new();
    let mut at = 0;
    while at < data.len() {
        let head = data.get(at..at + 8).ok_or_else(corrupt)?;
        let size = u32::from_be_bytes([head[0], head[1], head[2], head[3]]) as usize;
        if size < 8 || at + size > data.len() {
            return Err(corrupt());
        }
        out.push((
            [head[4], head[5], head[6], head[7]],
            &data[at + 8..at + size],
        ));
        at += size;
    }
    Ok(out)
}

pub(super) fn once<'a>(slot: &mut Option<&'a [u8]>, body: &'a [u8]) -> Result<()> {
    if slot.replace(body).is_some() {
        return Err(ambiguous());
    }
    Ok(())
}

pub(super) fn be32(bytes: &[u8], at: usize) -> Result<u64> {
    let slice = bytes.get(at..at + 4).ok_or_else(corrupt)?;
    Ok(u64::from(u32::from_be_bytes([
        slice[0], slice[1], slice[2], slice[3],
    ])))
}

pub(super) fn be64(bytes: &[u8], at: usize) -> Result<u64> {
    let slice = bytes.get(at..at + 8).ok_or_else(corrupt)?;
    Ok(u64::from_be_bytes(slice.try_into().map_err(|_| corrupt())?))
}
