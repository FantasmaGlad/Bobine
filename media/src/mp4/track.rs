use super::*;

pub(super) fn header_times(body: &[u8]) -> Result<(u64, u64, u64)> {
    match body.first() {
        Some(0) => Ok((be32(body, 4)?, be32(body, 12)?, be32(body, 16)?)),
        Some(1) => Ok((be64(body, 4)?, be32(body, 20)?, be64(body, 24)?)),
        _ => Err(unsupported()),
    }
}

pub(super) fn year_of(unix: u64) -> u64 {
    let days = unix / 86_400 + 719_468;
    let era = days / 146_097;
    let day_of_era = days % 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let shifted_month = (5 * day_of_year + 2) / 153;
    let year = year_of_era + era * 400;
    if shifted_month >= 10 {
        year + 1
    } else {
        year
    }
}

pub(super) fn creation_year(stamp: u64) -> Result<Option<u64>> {
    if stamp == 0 {
        return Ok(None);
    }
    let unix = if stamp >= 2_082_844_800 {
        stamp - 2_082_844_800
    } else {
        stamp
    };
    let year = year_of(unix);
    if !(1000..=9999).contains(&year) {
        return Err(unsupported());
    }
    Ok(Some(year))
}

pub(super) struct Track {
    pub(super) seconds: f64,
    pub(super) creation: u64,
}

pub(super) fn track(body: &[u8], movie_scale: u64) -> Result<Track> {
    let mut edits = None;
    let mut media = None;
    for (kind, inner) in boxes(body)? {
        match &kind {
            b"tkhd" => {}
            b"edts" => once(&mut edits, inner)?,
            b"mdia" => once(&mut media, inner)?,
            _ => return Err(unsupported()),
        }
    }
    let media = media.ok_or_else(corrupt)?;
    let (mut mdhd, mut hdlr, mut minf) = (None, None, None);
    for (kind, inner) in boxes(media)? {
        match &kind {
            b"mdhd" => once(&mut mdhd, inner)?,
            b"hdlr" => once(&mut hdlr, inner)?,
            b"minf" => once(&mut minf, inner)?,
            _ => return Err(unsupported()),
        }
    }
    let (mdhd, hdlr, minf) = (
        mdhd.ok_or_else(corrupt)?,
        hdlr.ok_or_else(corrupt)?,
        minf.ok_or_else(corrupt)?,
    );
    if hdlr.get(8..12) != Some(b"soun") {
        return Err(unsupported());
    }
    sample_table(minf)?;
    let (creation, scale, duration) = header_times(mdhd)?;
    if scale == 0 {
        return Err(corrupt());
    }
    let seconds = match edits {
        Some(edits) => {
            let list = boxes(edits)?;
            let [(kind, elst)] = list.as_slice() else {
                return Err(unsupported());
            };
            if kind != b"elst" {
                return Err(unsupported());
            }
            let wide = match elst.first() {
                Some(0) => false,
                Some(1) => true,
                _ => return Err(unsupported()),
            };
            if be32(elst, 4)? != 1 {
                return Err(unsupported());
            }
            let (segment, start, rate) = if wide {
                (be64(elst, 8)?, be64(elst, 16)? as i64, be32(elst, 24)?)
            } else {
                (
                    be32(elst, 8)?,
                    i64::from(be32(elst, 12)? as u32 as i32),
                    be32(elst, 16)?,
                )
            };
            if start < 0 || rate != 0x0001_0000 {
                return Err(unsupported());
            }
            segment as f64 / movie_scale as f64
        }
        None => duration as f64 / scale as f64,
    };
    Ok(Track { seconds, creation })
}

pub(super) fn sample_table(minf: &[u8]) -> Result<()> {
    let mut table = None;
    for (kind, inner) in boxes(minf)? {
        match &kind {
            b"smhd" | b"dinf" => {}
            b"stbl" => once(&mut table, inner)?,
            _ => return Err(unsupported()),
        }
    }
    let table = table.ok_or_else(corrupt)?;
    let mut description = None;
    for (kind, inner) in boxes(table)? {
        match &kind {
            b"stsd" => once(&mut description, inner)?,
            b"stts" | b"stsc" | b"stsz" | b"stz2" | b"stco" | b"co64" | b"sgpd" | b"sbgp"
            | b"stss" | b"ctts" => {}
            _ => return Err(unsupported()),
        }
    }
    let description = description.ok_or_else(corrupt)?;
    if be32(description, 4)? != 1 || !matches!(description.get(12..16), Some(b"mp4a" | b"alac")) {
        return Err(unsupported());
    }
    Ok(())
}
