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
    let serial = first.serial;
    let mut packets = Packets::default();
    let (codec, headers) = read_headers(reader, &mut packets, &first)?;
    let mut layout = Layout::default();
    vorbis::read(
        comment_body(&codec, &headers[1])?,
        &mut layout,
        Pictures::Base64Comment,
        want_cover,
    )?;
    let (rate, first_granule) = first_audio_page(reader, &mut packets, &codec, &headers, serial)?;
    let (flags, granule, last_serial) = last_page(reader, file_len)?;
    if last_serial != serial
        || flags & 0x04 == 0
        || granule == NO_GRANULE
        || granule < first_granule
        || granule == 0
    {
        return Err(unsupported());
    }
    layout.duration = Duration::Exact(granule as f64 / rate as f64);
    Ok(layout)
}

fn read_headers<R: Read>(
    reader: &mut R,
    packets: &mut Packets,
    first: &Page,
) -> Result<(Codec, Vec<Vec<u8>>)> {
    let ident = packets.feed(first)?;
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
    let mut headers = vec![ident.clone()];
    while headers.len() < needed {
        let page = read_page(reader)?;
        if page.serial != first.serial || page.flags & 0x06 != 0 {
            return Err(unsupported());
        }
        headers.extend(packets.feed(&page)?);
        if headers.len() > needed || (headers.len() == needed && !packets.partial.is_empty()) {
            return Err(unsupported());
        }
    }
    Ok((codec, headers))
}

fn comment_body<'a>(codec: &Codec, comment: &'a [u8]) -> Result<&'a [u8]> {
    match codec {
        Codec::Vorbis { .. } => {
            if !comment.starts_with(b"\x03vorbis")
                || comment.last() != Some(&1)
                || comment.len() < 8
            {
                return Err(unsupported());
            }
            Ok(&comment[7..comment.len() - 1])
        }
        Codec::Opus => {
            if !comment.starts_with(b"OpusTags") {
                return Err(unsupported());
            }
            Ok(&comment[8..])
        }
    }
}

fn first_audio_page<R: Read>(
    reader: &mut R,
    packets: &mut Packets,
    codec: &Codec,
    headers: &[Vec<u8>],
    serial: u32,
) -> Result<(u64, u64)> {
    let data = read_page(reader)?;
    if data.serial != serial || data.flags & 0x02 != 0 || data.granule == NO_GRANULE {
        return Err(unsupported());
    }
    let completed = packets.feed(&data)?;
    let (rate, expected) = match codec {
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
    Ok((rate, data.granule))
}
