use super::*;

pub(super) const MAX_PAGE_BYTES: usize = 27 + 255 + 255 * 255;

pub(super) const NO_GRANULE: u64 = u64::MAX;

pub(super) struct Page {
    pub(super) flags: u8,
    pub(super) granule: u64,
    pub(super) serial: u32,
    pub(super) segments: Vec<u8>,
    pub(super) body: Vec<u8>,
}

pub(super) fn header(bytes: &[u8]) -> Option<(u8, u64, u32, usize, usize)> {
    if bytes.len() < 27 || &bytes[..4] != b"OggS" || bytes[4] != 0 {
        return None;
    }
    let segments = usize::from(bytes[26]);
    let table = bytes.get(27..27 + segments)?;
    let body: usize = table.iter().map(|lacing| usize::from(*lacing)).sum();
    let granule = u64::from_le_bytes(bytes[6..14].try_into().ok()?);
    let serial = u32::from_le_bytes(bytes[14..18].try_into().ok()?);
    Some((bytes[5], granule, serial, segments, 27 + segments + body))
}

pub(super) fn read_page<R: Read>(reader: &mut R) -> Result<Page> {
    let mut head = [0; 27];
    read_exact(reader, &mut head)?;
    let count = usize::from(head[26]);
    let mut segments = vec![0; count];
    read_exact(reader, &mut segments)?;
    let (flags, granule, serial, _, _) =
        header(&[head.as_slice(), segments.as_slice()].concat()).ok_or_else(corrupt)?;
    let size: usize = segments.iter().map(|lacing| usize::from(*lacing)).sum();
    let mut body = vec![0; size];
    read_exact(reader, &mut body)?;
    Ok(Page {
        flags,
        granule,
        serial,
        segments,
        body,
    })
}

#[derive(Default)]
pub(super) struct Packets {
    pub(super) partial: Vec<u8>,
}

impl Packets {
    pub(super) fn feed(&mut self, page: &Page) -> Result<Vec<Vec<u8>>> {
        if (page.flags & 1 != 0) != !self.partial.is_empty() {
            return Err(corrupt());
        }
        let mut done = Vec::new();
        let mut at = 0;
        for lacing in &page.segments {
            let end = at + usize::from(*lacing);
            self.partial.extend_from_slice(&page.body[at..end]);
            if self.partial.len() > MAX_METADATA_BYTES + 65_536 {
                return Err(limit());
            }
            at = end;
            if *lacing < 255 {
                done.push(std::mem::take(&mut self.partial));
            }
        }
        Ok(done)
    }
}

pub(super) fn last_page<R: Read + Seek>(reader: &mut R, file_len: u64) -> Result<(u8, u64, u32)> {
    let window = file_len.min(MAX_PAGE_BYTES as u64 + 27);
    reader
        .seek(SeekFrom::Start(file_len - window))
        .map_err(|_| corrupt())?;
    let mut bytes = vec![0; window as usize];
    read_exact(reader, &mut bytes)?;
    let mut candidate = 0;
    while candidate + 4 <= bytes.len() {
        if &bytes[candidate..candidate + 4] != b"OggS" {
            candidate += 1;
            continue;
        }
        let mut at = candidate;
        while let Some((flags, granule, serial, _, length)) = header(&bytes[at..]) {
            if at + length > bytes.len() {
                break;
            }
            at += length;
            if at == bytes.len() {
                return Ok((flags, granule, serial));
            }
        }
        candidate += 1;
    }
    Err(unsupported())
}
