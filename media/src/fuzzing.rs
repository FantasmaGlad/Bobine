use std::io::Cursor;

pub enum Format {
    Mp3,
    Flac,
    Wav,
    Mp4,
    Ogg,
    Aiff,
}

pub fn scan(format: Format, data: &[u8], cover_only: bool) {
    let length = data.len() as u64;
    let mut reader = Cursor::new(data);
    let _ = match format {
        Format::Mp3 => crate::mp3::scan(&mut reader, length, cover_only),
        Format::Flac => crate::flac::scan(&mut reader, length, cover_only),
        Format::Wav => crate::wav::scan(&mut reader, length),
        Format::Mp4 => crate::mp4::scan(&mut reader, length, cover_only),
        Format::Ogg => crate::ogg::scan(&mut reader, length, cover_only),
        Format::Aiff => crate::aiff::scan(&mut reader, length),
    };
}

pub fn image(data: &[u8]) {
    let _ = crate::image::classify(data, None);
    let _ = crate::image::base64_decode(data);
}
