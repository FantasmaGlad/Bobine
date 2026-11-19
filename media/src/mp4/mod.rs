use crate::audio::{
    ambiguous, corrupt, cover_error, insert, limit, read_exact, unsupported, Duration, Layout,
    Picture, Result, MAX_TEXT_BYTES,
};
use crate::COVER_BYTES;
use std::io::{Read, Seek, SeekFrom};

mod boxes;
mod meta;
#[cfg(test)]
mod tests;
mod track;

use boxes::*;
use meta::*;
use track::*;

const MAX_MOOV_BYTES: u64 = 12 * 1024 * 1024;

fn read_moov(moov: &[u8], layout: &mut Layout, want_cover: bool) -> Result<()> {
    let (mut header, mut audio, mut user) = (None, None, None);
    for (kind, inner) in boxes(moov)? {
        match &kind {
            b"mvhd" => once(&mut header, inner)?,
            b"trak" => once(&mut audio, inner)?,
            b"udta" => once(&mut user, inner)?,
            b"iods" | b"free" | b"skip" => {}
            _ => return Err(unsupported()),
        }
    }
    let header = header.ok_or_else(corrupt)?;
    let (movie_created, movie_scale, movie_duration) = header_times(header)?;
    if movie_scale == 0 {
        return Err(corrupt());
    }
    let audio = track(audio.ok_or_else(unsupported)?, movie_scale)?;
    let movie_seconds = movie_duration as f64 / movie_scale as f64;
    if !movie_seconds.is_finite() || (movie_seconds - audio.seconds).abs() > 0.001 {
        return Err(ambiguous());
    }
    if let Some(user) = user {
        for (kind, inner) in boxes(user)? {
            match &kind {
                b"meta" => read_meta(inner, layout, want_cover)?,
                b"free" => {}
                _ => return Err(unsupported()),
            }
        }
    }
    let created = if movie_created != 0 {
        movie_created
    } else {
        audio.creation
    };
    if let Some(year) = creation_year(created)? {
        insert(&mut layout.tags, "creation_time", format!("{year:04}"))?;
    }
    layout.duration = Duration::Exact(movie_seconds);
    Ok(())
}

fn box_header<R: Read>(
    reader: &mut R,
    position: u64,
    file_len: u64,
) -> Result<([u8; 4], u64, u64)> {
    if file_len - position < 8 {
        return Err(corrupt());
    }
    let mut head = [0; 8];
    read_exact(reader, &mut head)?;
    let kind = [head[4], head[5], head[6], head[7]];
    let mut header = 8_u64;
    let mut size = u64::from(u32::from_be_bytes([head[0], head[1], head[2], head[3]]));
    if size == 1 {
        let mut wide = [0; 8];
        read_exact(reader, &mut wide)?;
        size = u64::from_be_bytes(wide);
        header = 16;
    } else if size == 0 {
        size = file_len - position;
    }
    if size < header || size > file_len - position {
        return Err(corrupt());
    }
    Ok((kind, size, size - header))
}

fn read_brand<R: Read>(reader: &mut R, position: u64, body: u64) -> Result<()> {
    if position != 0 || !(8..=256).contains(&body) {
        return Err(unsupported());
    }
    let mut data = vec![0; body as usize];
    read_exact(reader, &mut data)?;
    if !matches!(&data[..4], b"M4A " | b"isom" | b"mp42") {
        return Err(unsupported());
    }
    Ok(())
}

fn read_moov_box<R: Read>(reader: &mut R, body: u64, moov: &mut Option<Vec<u8>>) -> Result<()> {
    if moov.is_some() {
        return Err(ambiguous());
    }
    if body > MAX_MOOV_BYTES {
        return Err(limit());
    }
    let mut data = vec![0; body as usize];
    read_exact(reader, &mut data)?;
    *moov = Some(data);
    Ok(())
}

pub(crate) fn scan<R: Read + Seek>(
    reader: &mut R,
    file_len: u64,
    want_cover: bool,
) -> Result<Layout> {
    let mut position = 0_u64;
    let mut brand_seen = false;
    let mut moov: Option<Vec<u8>> = None;
    while position < file_len {
        let (kind, size, body) = box_header(reader, position, file_len)?;
        match &kind {
            b"ftyp" => {
                read_brand(reader, position, body)?;
                brand_seen = true;
            }
            _ if !brand_seen => return Err(unsupported()),
            b"moov" => read_moov_box(reader, body, &mut moov)?,
            b"mdat" | b"free" | b"skip" | b"wide" => {
                reader
                    .seek(SeekFrom::Current(body as i64))
                    .map_err(|_| corrupt())?;
            }
            _ => return Err(unsupported()),
        }
        position += size;
    }
    let mut layout = Layout::default();
    read_moov(&moov.ok_or_else(corrupt)?, &mut layout, want_cover)?;
    Ok(layout)
}
