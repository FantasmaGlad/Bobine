use crate::audio::{
    corrupt, limit, read_exact, unsupported, Duration, Layout, Result, MAX_METADATA_BYTES,
};
use crate::vorbis::{self, Pictures};
use std::io::{Read, Seek, SeekFrom};

mod codec;
mod page;
#[cfg(test)]
mod tests;

use codec::*;
use page::*;

pub(crate) fn scan<R: Read + Seek>(
    reader: &mut R,
    file_len: u64,
    want_cover: bool,
) -> Result<Layout> {
    let first = read_page(reader)?;
    if first.flags != 0x02 {
        return Err(unsupported());
    }
    let mut packets = Packets::default();
    let ident = packets.feed(&first)?;
    let [ident] = ident.as_slice() else {
        return Err(unsupported());
    };
    if !packets.partial.is_empty() {
        return Err(unsupported());
    }
    let codec = identify(ident)?;
    let needed = if matches!(codec, Codec::Vorbis { .. }) {
        3
    } else {
        2
    };
    let serial = first.serial;
    let mut headers = vec![ident.clone()];
    while headers.len() < needed {
        let page = read_page(reader)?;
        if page.serial != serial || page.flags & 0x06 != 0 {
            return Err(unsupported());
        }
        headers.extend(packets.feed(&page)?);
        if headers.len() > needed || (headers.len() == needed && !packets.partial.is_empty()) {
            return Err(unsupported());
        }
    }
    let mut layout = Layout::default();
    let comment = &headers[1];
    let content = match codec {
        Codec::Vorbis { .. } => {
            if !comment.starts_with(b"\x03vorbis")
                || comment.last() != Some(&1)
                || comment.len() < 8
            {
                return Err(unsupported());
            }
            &comment[7..comment.len() - 1]
        }
        Codec::Opus => {
            if !comment.starts_with(b"OpusTags") {
                return Err(unsupported());
            }
            &comment[8..]
        }
    };
    vorbis::read(content, &mut layout, Pictures::Base64Comment, want_cover)?;

    let data = read_page(reader)?;
    if data.serial != serial || data.flags & 0x02 != 0 || data.granule == NO_GRANULE {
        return Err(unsupported());
    }
    let completed = packets.feed(&data)?;
    let (rate, expected) = match &codec {
        Codec::Vorbis { rate, short, long } => {
            let table = modes(&headers[2])?;
            (*rate, vorbis_total(&completed, &table, *short, *long)?)
        }
        Codec::Opus => (
            48_000,
            completed.iter().try_fold(0_u64, |total, packet| {
                Ok::<u64, crate::MediaError>(total + opus_samples(packet)?)
            })?,
        ),
    };
    if data.granule != expected {
        return Err(unsupported());
    }
    let (flags, granule, last_serial) = last_page(reader, file_len)?;
    if last_serial != serial
        || flags & 0x04 == 0
        || granule == NO_GRANULE
        || granule < data.granule
        || granule == 0
    {
        return Err(unsupported());
    }
    layout.duration = Duration::Exact(granule as f64 / rate as f64);
    Ok(layout)
}
