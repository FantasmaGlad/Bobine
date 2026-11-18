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
    let tags = scan(&mut Cursor::new(&bitmap), bitmap.len() as u64, false).unwrap();
    assert_eq!(tags.pictures, 1);
}

#[test]
fn unknown_items_boxes_and_layouts_are_refused() {
    let track = || track_box(Some((1370, 1024)), 61_441, b"mp4a");
    for items in [
        item(b"----", 1, b"x"),
        item(b"gnre", 0, &[0, 12]),
        [item(b"\xa9nam", 1, b"A"), item(b"\xa9nam", 1, b"B")].concat(),
        item(b"\xa9nam", 2, b"A"),
    ] {
        assert!(scanned(&file(&items, (0, 1000, 1370), track())).is_err());
    }
    let mut fragmented = file(&[], (0, 1000, 1370), track());
    fragmented.extend(atom(b"moof", &[]));
    assert_eq!(scanned(&fragmented).unwrap_err().reason, "unsupported");
    let mut branded = file(&[], (0, 1000, 1370), track());
    branded[8..12].copy_from_slice(b"qt  ");
    assert_eq!(scanned(&branded).unwrap_err().reason, "unsupported");
    assert_eq!(scanned(&[]).unwrap_err().reason, "corrupt");
}

#[test]
fn box_size_past_the_address_space_is_corrupt() {
    let mut data = atom(b"free", &[0; 8]);
    data.extend_from_slice(&u32::MAX.to_be_bytes());
    data.extend_from_slice(b"moov");
    assert!(boxes(&data).is_err());
}
