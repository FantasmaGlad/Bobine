//! MPEG-4 audio (`.m4a`): one progressive audio track and iTunes-style `ilst` metadata.
//!
//! The container is read from its `moov` box alone, never decoded. The duration is the
//! movie header's (`mvhd`), the value ffprobe reports as the format duration, accepted only
//! when the track agrees with it (edit list, else media header) within a millisecond.
//! Fragmented files, several tracks, QuickTime keys, free-form items and anything not
//! listed below use the reference path.

use crate::audio::{
    ambiguous, corrupt, cover_error, insert, limit, read_exact, unsupported, Duration, Layout,
    Picture, Result, MAX_TEXT_BYTES,
};
use crate::COVER_BYTES;
use std::io::{Read, Seek, SeekFrom};

const MAX_MOOV_BYTES: u64 = 12 * 1024 * 1024;

type Boxes<'a> = Vec<([u8; 4], &'a [u8])>;

/// The boxes laid out one after the other in `data`; any irregular size is corrupt.
fn boxes(data: &[u8]) -> Result<Boxes<'_>> {
    let mut out = Vec::new();
    let mut at = 0;
    while at < data.len() {
        let head = data.get(at..at + 8).ok_or_else(corrupt)?;
        let size = u32::from_be_bytes([head[0], head[1], head[2], head[3]]) as usize;
        // Large and to-the-end sizes only make sense at the top level.
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

fn once<'a>(slot: &mut Option<&'a [u8]>, body: &'a [u8]) -> Result<()> {
    if slot.replace(body).is_some() {
        return Err(ambiguous());
    }
    Ok(())
}

fn be32(bytes: &[u8], at: usize) -> Result<u64> {
    let slice = bytes.get(at..at + 4).ok_or_else(corrupt)?;
    Ok(u64::from(u32::from_be_bytes([
        slice[0], slice[1], slice[2], slice[3],
    ])))
}

fn be64(bytes: &[u8], at: usize) -> Result<u64> {
    let slice = bytes.get(at..at + 8).ok_or_else(corrupt)?;
    Ok(u64::from_be_bytes(slice.try_into().map_err(|_| corrupt())?))
}

/// (creation time, timescale, duration) of an `mvhd` or `mdhd` box, version 0 or 1.
fn header_times(body: &[u8]) -> Result<(u64, u64, u64)> {
    match body.first() {
        Some(0) => Ok((be32(body, 4)?, be32(body, 12)?, be32(body, 16)?)),
        Some(1) => Ok((be64(body, 4)?, be32(body, 20)?, be64(body, 24)?)),
        _ => Err(unsupported()),
    }
}

/// The calendar year of a Unix time, by the civil-from-days algorithm.
fn year_of(unix: u64) -> u64 {
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

/// ffmpeg's `creation_time` tag, of which only the year matters to the application. A value
/// below the 1904 offset is taken as a Unix time, as ffmpeg does; years outside four digits
/// are left to the reference.
fn creation_year(stamp: u64) -> Result<Option<u64>> {
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

struct Track {
    /// Duration of the track in seconds: edit list when present, else the media header.
    seconds: f64,
    creation: u64,
}

fn track(body: &[u8], movie_scale: u64) -> Result<Track> {
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
            // One ordinary edit at normal speed; an empty edit or a rate change shifts timing.
            if start < 0 || rate != 0x0001_0000 {
                return Err(unsupported());
            }
            segment as f64 / movie_scale as f64
        }
        None => duration as f64 / scale as f64,
    };
    Ok(Track { seconds, creation })
}

/// The sample table of the media: AAC or ALAC, and only boxes that carry no timing rule.
fn sample_table(minf: &[u8]) -> Result<()> {
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

/// Text item: exactly one UTF-8 `data` box.
fn text_item(item: &[u8]) -> Result<String> {
    let payload = single_data(item, 1)?;
    if payload.is_empty() || payload.len() > MAX_TEXT_BYTES {
        return Err(unsupported());
    }
    String::from_utf8(payload.to_vec()).map_err(|_| corrupt())
}

/// The payload of the only `data` box of an item, whose type indicator must be `kind`.
fn single_data(item: &[u8], kind: u32) -> Result<&[u8]> {
    let list = boxes(item)?;
    let [(name, data)] = list.as_slice() else {
        return Err(unsupported());
    };
    if name != b"data" || data.len() < 8 || be32(data, 0)? != u64::from(kind) {
        return Err(unsupported());
    }
    Ok(&data[8..])
}

/// iTunes numbering (`trkn`, `disk`): two reserved bytes, number, total, two reserved bytes.
/// ffmpeg prints a signed 16-bit number and the total only when it is not zero.
fn number_item(item: &[u8]) -> Result<String> {
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

fn read_meta(meta: &[u8], layout: &mut Layout, want_cover: bool) -> Result<()> {
    // `meta` is a full box: version and flags precede its children.
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
    // QuickTime-style `keys` metadata has another structure.
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
            // Items ffmpeg exports under names the application never reads.
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
    // ffmpeg tags the movie, then the stream, with their creation times; the first wins.
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

pub(crate) fn scan<R: Read + Seek>(
    reader: &mut R,
    file_len: u64,
    want_cover: bool,
) -> Result<Layout> {
    let mut position = 0_u64;
    let mut brand_seen = false;
    let mut moov: Option<Vec<u8>> = None;
    while position < file_len {
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
        let body = size - header;
        match &kind {
            b"ftyp" => {
                if position != 0 || !(8..=256).contains(&body) {
                    return Err(unsupported());
                }
                let mut data = vec![0; body as usize];
                read_exact(reader, &mut data)?;
                if !matches!(&data[..4], b"M4A " | b"isom" | b"mp42") {
                    return Err(unsupported());
                }
                brand_seen = true;
            }
            _ if !brand_seen => return Err(unsupported()),
            b"moov" => {
                if moov.is_some() {
                    return Err(ambiguous());
                }
                if body > MAX_MOOV_BYTES {
                    return Err(limit());
                }
                let mut data = vec![0; body as usize];
                read_exact(reader, &mut data)?;
                moov = Some(data);
            }
            b"mdat" | b"free" | b"skip" | b"wide" => {
                reader
                    .seek(SeekFrom::Current(body as i64))
                    .map_err(|_| corrupt())?;
            }
            // Fragments, segment indexes, uuid boxes, a top-level meta: not this layout.
            _ => return Err(unsupported()),
        }
        position += size;
    }
    let mut layout = Layout::default();
    read_moov(&moov.ok_or_else(corrupt)?, &mut layout, want_cover)?;
    Ok(layout)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn atom(kind: &[u8; 4], body: &[u8]) -> Vec<u8> {
        let mut bytes = ((body.len() + 8) as u32).to_be_bytes().to_vec();
        bytes.extend_from_slice(kind);
        bytes.extend_from_slice(body);
        bytes
    }

    fn full(kind: &[u8; 4], version: u8, body: &[u8]) -> Vec<u8> {
        atom(kind, &[&[version, 0, 0, 0], body].concat())
    }

    fn header(kind: &[u8; 4], created: u32, scale: u32, duration: u32) -> Vec<u8> {
        let mut body = created.to_be_bytes().to_vec();
        body.extend_from_slice(&[0; 4]);
        body.extend_from_slice(&scale.to_be_bytes());
        body.extend_from_slice(&duration.to_be_bytes());
        body.resize(body.len() + 80, 0);
        full(kind, 0, &body)
    }

    fn item(kind: &[u8; 4], type_indicator: u32, payload: &[u8]) -> Vec<u8> {
        let mut data = type_indicator.to_be_bytes().to_vec();
        data.extend_from_slice(&[0; 4]);
        data.extend_from_slice(payload);
        atom(kind, &atom(b"data", &data))
    }

    fn track_box(edit: Option<(u32, i32)>, media_duration: u32, codec: &[u8; 4]) -> Vec<u8> {
        let mut media = header(b"mdhd", 0, 44_100, media_duration);
        let mut hdlr = vec![0; 4];
        hdlr.extend_from_slice(b"soun");
        hdlr.resize(hdlr.len() + 13, 0);
        media.extend(full(b"hdlr", 0, &hdlr));
        let stsd = full(
            b"stsd",
            0,
            &[
                1_u32.to_be_bytes().as_slice(),
                &(16_u32).to_be_bytes(),
                codec,
                &[0; 8],
            ]
            .concat(),
        );
        let table = [stsd, full(b"stts", 0, &[0; 4])].concat();
        let minf = [full(b"smhd", 0, &[0; 4]), atom(b"stbl", &table)].concat();
        media.extend(atom(b"minf", &minf));
        let mut body = full(b"tkhd", 0, &[0; 80]);
        if let Some((segment, start)) = edit {
            let mut elst = 1_u32.to_be_bytes().to_vec();
            elst.extend_from_slice(&segment.to_be_bytes());
            elst.extend_from_slice(&start.to_be_bytes());
            elst.extend_from_slice(&0x0001_0000_u32.to_be_bytes());
            body.extend(atom(b"edts", &full(b"elst", 0, &elst)));
        }
        body.extend(atom(b"mdia", &media));
        atom(b"trak", &body)
    }

    fn file(moov_items: &[u8], movie: (u32, u32, u32), track: Vec<u8>) -> Vec<u8> {
        let mut meta = full(
            b"hdlr",
            0,
            &[&[0; 4], b"mdir".as_slice(), &[0; 13]].concat(),
        );
        meta.extend(atom(b"ilst", moov_items));
        let udta = atom(b"udta", &full(b"meta", 0, &meta)[..]);
        let moov = atom(
            b"moov",
            &[header(b"mvhd", movie.0, movie.1, movie.2), track, udta].concat(),
        );
        [
            atom(b"ftyp", b"M4A \0\0\x02\0M4A isom"),
            atom(b"free", &[]),
            atom(b"mdat", &[1; 40]),
            moov,
        ]
        .concat()
    }

    fn scanned(bytes: &[u8]) -> Result<Layout> {
        scan(&mut Cursor::new(bytes), bytes.len() as u64, true)
    }

    #[test]
    fn years_from_unix_time() {
        assert_eq!(year_of(0), 1970);
        assert_eq!(year_of(951_782_400), 2000); // 2000-02-29
        assert_eq!(year_of(1_704_067_199), 2023);
        assert_eq!(year_of(1_704_067_200), 2024);
        assert_eq!(creation_year(0).unwrap(), None);
        assert_eq!(creation_year(100).unwrap(), Some(1970));
        assert_eq!(
            creation_year(2_082_844_800 + 1_704_067_200).unwrap(),
            Some(2024)
        );
    }

    #[test]
    fn duration_is_the_movie_header_checked_against_the_track() {
        let items = [
            item(b"\xa9nam", 1, "Été".as_bytes()),
            item(b"trkn", 0, &[0, 0, 0, 3, 0, 12, 0, 0]),
        ]
        .concat();
        let bytes = file(
            &items,
            (0, 1000, 1370),
            track_box(Some((1370, 1024)), 61_441, b"mp4a"),
        );
        let layout = scanned(&bytes).unwrap();
        assert_eq!(layout.duration, Duration::Exact(1.37));
        assert_eq!(layout.tags["title"], "Été");
        assert_eq!(layout.tags["track"], "3/12");
        // Without an edit list the media header decides; a disagreement is refused.
        let plain = file(&[], (0, 44_100, 61_441), track_box(None, 61_441, b"alac"));
        assert!(scanned(&plain).is_ok());
        let off = file(&[], (0, 44_100, 61_441), track_box(None, 70_000, b"mp4a"));
        assert_eq!(scanned(&off).unwrap_err().reason, "ambiguous_metadata");
        let moved = file(
            &[],
            (0, 1000, 1370),
            track_box(Some((1370, -1)), 61_441, b"mp4a"),
        );
        assert_eq!(scanned(&moved).unwrap_err().reason, "unsupported");
    }

    #[test]
    fn numbering_follows_ffmpeg_formatting() {
        let number = |bytes: [u8; 8]| number_item(&item(b"trkn", 0, &bytes)[8..]).unwrap();
        assert_eq!(number([0, 0, 0, 5, 0, 0, 0, 0]), "5");
        assert_eq!(number([0, 0, 0, 0, 0, 9, 0, 0]), "0/9");
        assert!(number_item(&item(b"trkn", 0, &[0, 0, 0x80, 0, 0, 0, 0, 0])[8..]).is_err());
        assert!(number_item(&item(b"trkn", 1, &[0, 0, 0, 1, 0, 0, 0, 0])[8..]).is_err());
    }

    #[test]
    fn creation_time_is_a_year_source() {
        let movie = file(
            &[],
            (3_786_912_000, 1000, 1370),
            track_box(Some((1370, 1024)), 61_441, b"mp4a"),
        );
        assert_eq!(scanned(&movie).unwrap().tags["creation_time"], "2024");
        let none = file(
            &[],
            (0, 1000, 1370),
            track_box(Some((1370, 1024)), 61_441, b"mp4a"),
        );
        assert!(!scanned(&none).unwrap().tags.contains_key("creation_time"));
    }

    #[test]
    fn covers_are_counted_and_typed() {
        let jpeg = [0xff, 0xd8, 0xff, 0xd9];
        let single = file(
            &item(b"covr", 13, &jpeg),
            (0, 1000, 1370),
            track_box(Some((1370, 1024)), 61_441, b"mp4a"),
        );
        let layout = scanned(&single).unwrap();
        assert_eq!(layout.pictures, 1);
        assert_eq!(
            layout.picture.unwrap().declared.as_deref(),
            Some("image/jpeg")
        );
        let bitmap = file(
            &item(b"covr", 27, &jpeg),
            (0, 1000, 1370),
            track_box(Some((1370, 1024)), 61_441, b"mp4a"),
        );
        assert_eq!(scanned(&bitmap).unwrap_err().reason, "ambiguous_cover");
        // The tags of a file whose picture is not eligible are still read.
        let tags = scan(&mut Cursor::new(&bitmap), bitmap.len() as u64, false).unwrap();
        assert_eq!(tags.pictures, 1);
    }

    #[test]
    fn unknown_items_boxes_and_layouts_are_refused() {
        let track = || track_box(Some((1370, 1024)), 61_441, b"mp4a");
        // Free-form item, a genre index, a duplicate title.
        for items in [
            item(b"----", 1, b"x"),
            item(b"gnre", 0, &[0, 12]),
            [item(b"\xa9nam", 1, b"A"), item(b"\xa9nam", 1, b"B")].concat(),
            item(b"\xa9nam", 2, b"A"),
        ] {
            assert!(scanned(&file(&items, (0, 1000, 1370), track())).is_err());
        }
        // Fragmented file, no brand, extra top-level box.
        let mut fragmented = file(&[], (0, 1000, 1370), track());
        fragmented.extend(atom(b"moof", &[]));
        assert_eq!(scanned(&fragmented).unwrap_err().reason, "unsupported");
        let mut branded = file(&[], (0, 1000, 1370), track());
        branded[8..12].copy_from_slice(b"qt  ");
        assert_eq!(scanned(&branded).unwrap_err().reason, "unsupported");
        assert_eq!(scanned(&[]).unwrap_err().reason, "corrupt");
    }
}
