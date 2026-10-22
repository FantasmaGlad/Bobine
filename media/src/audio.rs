use crate::{MediaError, COVER_BYTES};
use lofty::config::{apply_global_options, GlobalOptions, ParseOptions, ParsingMode};
use lofty::file::{AudioFile, FileType};
use lofty::probe::Probe;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{self, BufReader, Read, Seek, SeekFrom};
use std::path::Path;

const MAX_FILE_BYTES: u64 = 512 * 1024 * 1024;
const MAX_METADATA_BYTES: usize = 4 * 1024 * 1024;
const MAX_TEXT_BYTES: usize = 64 * 1024;
const MAX_READ_BYTES: usize = 16 * 1024 * 1024;
/// Delay and padding are 12-bit sample counts: 2 x 4095 samples at 22.05 kHz at most.
const MAX_GAPLESS_TRIM_SECONDS: f64 = 0.4;

type Result<T> = std::result::Result<T, MediaError>;

fn corrupt() -> MediaError {
    MediaError::new("corrupt", "Invalid or truncated audio data")
}
fn unsupported() -> MediaError {
    MediaError::new(
        "unsupported",
        "Audio layout is outside the experimental subset",
    )
}
fn ambiguous() -> MediaError {
    MediaError::new(
        "ambiguous_metadata",
        "Metadata cannot be mapped without ambiguity",
    )
}
fn limit() -> MediaError {
    MediaError::new("limit_exceeded", "Media inspection limit exceeded")
}
fn read_exact(reader: &mut impl Read, bytes: &mut [u8]) -> Result<()> {
    reader.read_exact(bytes).map_err(|error| {
        if error.kind() == io::ErrorKind::Other {
            limit()
        } else {
            corrupt()
        }
    })
}

#[derive(Default, Debug)]
struct Layout {
    tags: HashMap<String, String>,
    cover: bool,
    /// Duration computed by this crate when the container needs the reference rules
    /// (MP3 gapless trimming). `None` means Lofty's value is already equivalent.
    duration: Option<f64>,
}

/// A cumulative read budget supplements Lofty's per-item allocation bound.
struct BudgetReader<R> {
    inner: R,
    remaining: usize,
}
impl<R: Read> Read for BudgetReader<R> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        if buffer.is_empty() {
            return Ok(0);
        }
        if self.remaining == 0 {
            return Err(io::Error::other("media read budget exhausted"));
        }
        let limit = buffer.len().min(self.remaining);
        let read = self.inner.read(&mut buffer[..limit])?;
        self.remaining -= read;
        Ok(read)
    }
}
impl<R: Seek> Seek for BudgetReader<R> {
    fn seek(&mut self, position: SeekFrom) -> io::Result<u64> {
        self.inner.seek(position)
    }
}

pub(crate) fn inspect(path: &str, profile: &str, cover_only: bool) -> Result<Value> {
    let path = Path::new(path);
    if !path.is_absolute()
        || path.as_os_str().to_str().is_none()
        || path.to_string_lossy().contains('\0')
    {
        return Err(unsupported());
    }
    let info = std::fs::symlink_metadata(path).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            MediaError::new("not_found", "Media file does not exist")
        } else {
            MediaError::new("unreadable", "Media file cannot be read")
        }
    })?;
    // Reject symlinks and special files before open; only trusted local regular paths are accepted.
    if !info.file_type().is_file() {
        return Err(unsupported());
    }
    if info.len() > MAX_FILE_BYTES {
        return Err(limit());
    }
    let format = path
        .extension()
        .and_then(|extension| extension.to_str())
        .map(str::to_ascii_lowercase)
        .ok_or_else(unsupported)?;
    let kind = match format.as_str() {
        "mp3" => FileType::Mpeg,
        "flac" => FileType::Flac,
        "wav" => FileType::Wav,
        _ => return Err(unsupported()),
    };
    let file =
        File::open(path).map_err(|_| MediaError::new("unreadable", "Media file cannot be read"))?;
    let opened = file.metadata().map_err(|_| corrupt())?;
    if !opened.is_file()
        || opened.len() != info.len()
        || opened.modified().ok() != info.modified().ok()
    {
        return Err(MediaError::new(
            "unreadable",
            "Media changed during inspection",
        ));
    }
    let mut reader = BufReader::new(BudgetReader {
        inner: file,
        remaining: MAX_READ_BYTES,
    });
    let layout = match kind {
        FileType::Mpeg => scan_mp3(&mut reader, opened.len())?,
        FileType::Flac => scan_flac(&mut reader, opened.len())?,
        FileType::Wav => scan_wav(&mut reader, opened.len())?,
        _ => return Err(unsupported()),
    };
    if cover_only && layout.cover {
        return Err(MediaError::new(
            "ambiguous_cover",
            "Embedded images require the reference image pipeline",
        ));
    }
    reader.rewind().map_err(|_| corrupt())?;
    // These options are thread-local; apply them on every entry, including threaded tests.
    apply_global_options(
        GlobalOptions::new()
            .allocation_limit(MAX_METADATA_BYTES)
            .use_custom_resolvers(false)
            .preserve_format_specific_items(false),
    );
    let options = ParseOptions::new()
        .parsing_mode(ParsingMode::Strict)
        .implicit_conversions(false)
        .read_tags(false)
        .read_cover_art(false);
    let tagged = Probe::with_file_type(&mut reader, kind)
        .options(options)
        .read()
        .map_err(|_| {
            if reader.get_ref().remaining == 0 {
                limit()
            } else {
                corrupt()
            }
        })?;
    let parsed = tagged.properties().duration().as_secs_f64();
    if !parsed.is_finite() || parsed <= 0.0 {
        return Err(corrupt());
    }
    // The reference (ffprobe) removes the encoder delay and padding announced in the
    // LAME tag; Lofty reports the raw frame count. Two independent readings must agree
    // within the largest plausible trim before the reference rule is trusted.
    let duration = match layout.duration {
        Some(reference) if reference.is_finite() && reference > 0.0 => {
            if parsed - reference < -0.001 || parsed - reference > MAX_GAPLESS_TRIM_SECONDS {
                return Err(ambiguous());
            }
            reference
        }
        Some(_) => return Err(corrupt()),
        None => parsed,
    };
    let after = reader.get_ref().inner.metadata().map_err(|_| corrupt())?;
    if after.len() != opened.len() || after.modified().ok() != opened.modified().ok() {
        return Err(MediaError::new(
            "unreadable",
            "Media changed during inspection",
        ));
    }
    if cover_only {
        return Ok(json!({"status":"ok","cover":null}));
    }
    Ok(
        json!({"status":"ok","profile":profile,"format":format,"metadata":metadata(&layout.tags, duration)}),
    )
}

fn insert(tags: &mut HashMap<String, String>, key: &str, value: String) -> Result<()> {
    if value.len() > MAX_TEXT_BYTES || value.contains('\0') {
        return Err(limit());
    }
    let key = key.to_ascii_lowercase();
    if matches!(
        key.as_str(),
        "track"
            | "tracknumber"
            | "disc"
            | "discnumber"
            | "disk"
            | "date"
            | "year"
            | "originalyear"
            | "creation_time"
    ) && value
        .chars()
        .any(|character| character.is_numeric() && !character.is_ascii_digit())
    {
        // Python's Unicode decimal regex/int conversion needs separate parity work.
        return Err(unsupported());
    }
    if tags.insert(key, value).is_some() {
        return Err(ambiguous());
    }
    Ok(())
}

fn syncsafe(bytes: &[u8]) -> Result<usize> {
    if bytes.len() != 4 || bytes.iter().any(|byte| byte & 0x80 != 0) {
        return Err(corrupt());
    }
    Ok(bytes
        .iter()
        .fold(0, |size, byte| (size << 7) | usize::from(*byte)))
}

fn decode_text(bytes: &[u8]) -> Result<String> {
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
    // A trailing terminator is ordinary; multiple text values need an explicit merge policy.
    let text = text.trim_end_matches('\0').to_owned();
    if text.contains('\0') {
        return Err(ambiguous());
    }
    Ok(text)
}

fn scan_mp3<R: Read + Seek>(reader: &mut R, file_len: u64) -> Result<Layout> {
    if file_len < 16 {
        return Err(corrupt());
    }
    // ID3v1/APE coexistence is deliberately not merged with ID3v2.
    let tail_len = file_len.min(160) as usize;
    reader
        .seek(SeekFrom::End(-(tail_len as i64)))
        .map_err(|_| corrupt())?;
    let mut tail = vec![0; tail_len];
    read_exact(reader, &mut tail)?;
    if (tail_len >= 128 && &tail[tail_len - 128..tail_len - 125] == b"TAG")
        || tail.windows(8).any(|chunk| chunk == b"APETAGEX")
    {
        return Err(ambiguous());
    }
    reader.rewind().map_err(|_| corrupt())?;
    let mut header = [0; 10];
    read_exact(reader, &mut header)?;
    let mut layout = Layout::default();
    let mut audio_offset = 0;
    if &header[..3] == b"ID3" {
        let version = header[3];
        if !matches!(version, 3 | 4) || header[4] != 0 || header[5] != 0 {
            return Err(unsupported());
        }
        let size = syncsafe(&header[6..10])?;
        if size > MAX_METADATA_BYTES {
            return Err(limit());
        }
        if size as u64 + 14 > file_len {
            return Err(corrupt());
        }
        let mut content = vec![0; size];
        read_exact(reader, &mut content)?;
        let mut cursor = 0;
        let mut seen = HashSet::new();
        while cursor < content.len() {
            if content[cursor..].iter().all(|byte| *byte == 0) {
                break;
            }
            if content.len() - cursor < 10 {
                return Err(corrupt());
            }
            let frame = &content[cursor..cursor + 10];
            if frame[..4]
                .iter()
                .any(|byte| !byte.is_ascii_uppercase() && !byte.is_ascii_digit())
                || frame[8..10] != [0, 0]
            {
                return Err(unsupported());
            }
            let size = if version == 4 {
                syncsafe(&frame[4..8])?
            } else {
                u32::from_be_bytes(frame[4..8].try_into().map_err(|_| corrupt())?) as usize
            };
            let end = cursor
                .checked_add(10)
                .and_then(|start| start.checked_add(size))
                .filter(|end| *end <= content.len())
                .ok_or_else(corrupt)?;
            let key = match &frame[..4] {
                b"TIT2" => "title",
                b"TPE1" => "artist",
                b"TALB" => "album",
                b"TPE2" => "album_artist",
                b"TRCK" => "track",
                b"TPOS" => "disc",
                b"TDRC" | b"TYER" => "date",
                b"TCON" => "genre",
                b"TSSE" => "encoder",
                b"APIC" => "picture",
                _ => return Err(unsupported()),
            };
            if !seen.insert(key) {
                return Err(ambiguous());
            }
            let data = &content[cursor + 10..end];
            if key == "picture" {
                if data.len() > COVER_BYTES {
                    return Err(limit());
                }
                layout.cover = true;
            } else {
                if data.len() > MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let value = decode_text(data)?;
                if key == "genre"
                    && (value.starts_with('(')
                        || value.chars().any(|character| character.is_ascii_digit()))
                {
                    return Err(ambiguous());
                }
                if key != "encoder" {
                    insert(&mut layout.tags, key, value)?;
                }
            }
            cursor = end;
        }
        audio_offset = 10 + size as u64;
    }
    reader
        .seek(SeekFrom::Start(audio_offset))
        .map_err(|_| corrupt())?;
    let mut audio = [0; 4];
    read_exact(reader, &mut audio)?;
    // MPEG Layer III only, not a file disguised by its extension or leading junk.
    if audio[0] != 0xff || audio[1] & 0xe0 != 0xe0 || audio[1] & 6 != 2 {
        return Err(corrupt());
    }
    // Lofty's bitrate estimate diverges strongly for VBR without an index.
    // Require an explicit Xing/Info frame; VBRI and missing-index inputs use the oracle.
    let version_bits = (audio[1] >> 3) & 3;
    let mpeg1 = version_bits == 3;
    let mono = audio[3] >> 6 == 3;
    let sample_rate = match (version_bits, (audio[2] >> 2) & 3) {
        (3, 0) => 44_100,
        (3, 1) => 48_000,
        (3, 2) => 32_000,
        (2, 0) => 22_050,
        (2, 1) => 24_000,
        (2, 2) => 16_000,
        (0, 0) => 11_025,
        (0, 1) => 12_000,
        (0, 2) => 8_000,
        _ => return Err(corrupt()),
    };
    let samples_per_frame: u64 = if mpeg1 { 1152 } else { 576 };
    let side_info = match (mpeg1, mono) {
        (true, true) => 17,
        (true, false) => 32,
        (false, true) => 9,
        (false, false) => 17,
    };
    let crc = if audio[1] & 1 == 0 { 2 } else { 0 };
    reader
        .seek(SeekFrom::Start(audio_offset + 4 + crc + side_info))
        .map_err(|_| corrupt())?;
    let mut index = [0; 4];
    read_exact(reader, &mut index)?;
    if !matches!(&index, b"Xing" | b"Info") {
        return Err(unsupported());
    }
    layout.duration = Some(xing_duration(reader, samples_per_frame, sample_rate)?);
    Ok(layout)
}

/// Duration the reference (ffmpeg/ffprobe) reports for an MP3 with a Xing/Info frame.
///
/// The frame count is mandatory: without it ffmpeg falls back to a bitrate estimate that
/// this crate does not reproduce. Encoders named LAME, Lavf or Lavc add a 12-bit start
/// delay and a 12-bit end padding, which ffmpeg subtracts from the total; any other
/// encoder string leaves the plain `frames * samples_per_frame` count. Both rules were
/// checked against ffprobe on 148 generated files and on edited copies of one of them.
fn xing_duration<R: Read>(reader: &mut R, samples_per_frame: u64, sample_rate: u64) -> Result<f64> {
    let mut word = [0; 4];
    read_exact(reader, &mut word)?;
    let flags = u32::from_be_bytes(word);
    if flags & 1 == 0 {
        return Err(unsupported());
    }
    read_exact(reader, &mut word)?;
    let frames = u64::from(u32::from_be_bytes(word));
    if frames == 0 {
        return Err(unsupported());
    }
    let mut skip = [0; 100];
    if flags & 2 != 0 {
        read_exact(reader, &mut word)?;
    }
    if flags & 4 != 0 {
        read_exact(reader, &mut skip)?;
    }
    if flags & 8 != 0 {
        read_exact(reader, &mut word)?;
    }
    // Encoder (9), revision, lowpass, replay gain (8), flags, bitrate, then 3 delay bytes.
    let mut lame = [0; 24];
    read_exact(reader, &mut lame)?;
    let total = frames.checked_mul(samples_per_frame).ok_or_else(corrupt)?;
    let samples = if matches!(&lame[..4], b"LAME" | b"Lavf" | b"Lavc") {
        let delays = u32::from_be_bytes([0, lame[21], lame[22], lame[23]]);
        let trim = u64::from(delays >> 12) + u64::from(delays & 0xfff);
        if trim >= total {
            return Err(corrupt());
        }
        total - trim
    } else {
        total
    };
    Ok(samples as f64 / sample_rate as f64)
}

fn scan_flac<R: Read + Seek>(reader: &mut R, file_len: u64) -> Result<Layout> {
    let mut magic = [0; 4];
    read_exact(reader, &mut magic)?;
    if &magic != b"fLaC" {
        return Err(unsupported());
    }
    let mut layout = Layout::default();
    let mut position = 4_u64;
    let mut total = 0_usize;
    let mut comments_seen = false;
    for block_index in 0..128 {
        let mut header = [0; 4];
        read_exact(reader, &mut header)?;
        let kind = header[0] & 0x7f;
        let size =
            (usize::from(header[1]) << 16) | (usize::from(header[2]) << 8) | usize::from(header[3]);
        position += 4 + size as u64;
        total += size;
        if position > file_len {
            return Err(corrupt());
        }
        if total > MAX_METADATA_BYTES {
            return Err(limit());
        }
        if block_index == 0 && (kind != 0 || size != 34) {
            return Err(corrupt());
        }
        match kind {
            0 if block_index == 0 => {
                reader
                    .seek(SeekFrom::Current(size as i64))
                    .map_err(|_| corrupt())?;
            }
            1 | 3 => {
                reader
                    .seek(SeekFrom::Current(size as i64))
                    .map_err(|_| corrupt())?;
            }
            4 => {
                if comments_seen {
                    return Err(ambiguous());
                }
                comments_seen = true;
                if size > MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let mut content = vec![0; size];
                read_exact(reader, &mut content)?;
                read_vorbis(&content, &mut layout.tags)?;
            }
            6 => {
                layout.cover = true;
                reader
                    .seek(SeekFrom::Current(size as i64))
                    .map_err(|_| corrupt())?;
            }
            _ => return Err(unsupported()),
        }
        if header[0] & 0x80 != 0 {
            if position >= file_len {
                return Err(corrupt());
            }
            return Ok(layout);
        }
    }
    Err(limit())
}

fn read_vorbis(content: &[u8], tags: &mut HashMap<String, String>) -> Result<()> {
    fn take<'a>(content: &mut &'a [u8], size: usize) -> Result<&'a [u8]> {
        if content.len() < size {
            return Err(corrupt());
        }
        let (head, tail) = content.split_at(size);
        *content = tail;
        Ok(head)
    }
    fn number(content: &mut &[u8]) -> Result<usize> {
        Ok(u32::from_le_bytes(take(content, 4)?.try_into().map_err(|_| corrupt())?) as usize)
    }
    let mut input = content;
    let vendor_len = number(&mut input)?;
    take(&mut input, vendor_len)?;
    let count = number(&mut input)?;
    if count > 256 {
        return Err(limit());
    }
    for _ in 0..count {
        let length = number(&mut input)?;
        let item = std::str::from_utf8(take(&mut input, length)?).map_err(|_| corrupt())?;
        let (key, value) = item.split_once('=').ok_or_else(corrupt)?;
        let key = key.to_ascii_lowercase();
        match key.as_str() {
            "title" | "artist" | "author" | "performer" | "album" | "album_artist"
            | "albumartist" | "band" | "track" | "tracknumber" | "disc" | "discnumber" | "disk"
            | "date" | "year" | "originalyear" | "creation_time" | "genre" => {
                insert(tags, &key, value.to_owned())?
            }
            "encoder" | "comment" | "description" | "copyright" => {}
            _ => return Err(unsupported()),
        }
    }
    if !input.is_empty() {
        return Err(corrupt());
    }
    Ok(())
}

fn scan_wav<R: Read + Seek>(reader: &mut R, file_len: u64) -> Result<Layout> {
    let mut header = [0; 12];
    read_exact(reader, &mut header)?;
    if &header[..4] != b"RIFF" || &header[8..12] != b"WAVE" {
        return Err(unsupported());
    }
    let declared = u64::from(u32::from_le_bytes(
        header[4..8].try_into().map_err(|_| corrupt())?,
    )) + 8;
    if declared != file_len {
        return Err(unsupported());
    }
    let mut position = 12;
    let mut format_seen = false;
    let mut data_seen = false;
    let mut metadata_bytes = 0;
    for _ in 0..128 {
        if position == file_len {
            return if format_seen && data_seen {
                Ok(Layout::default())
            } else {
                Err(corrupt())
            };
        }
        let mut chunk = [0; 8];
        read_exact(reader, &mut chunk)?;
        let size = u32::from_le_bytes(chunk[4..8].try_into().map_err(|_| corrupt())?) as usize;
        position += 8 + size as u64 + (size % 2) as u64;
        if position > file_len {
            return Err(corrupt());
        }
        match &chunk[..4] {
            b"fmt " => {
                if format_seen || !matches!(size, 16 | 18) {
                    return Err(unsupported());
                }
                format_seen = true;
                let mut format = vec![0; size];
                read_exact(reader, &mut format)?;
                if format[..2] != [1, 0] {
                    return Err(unsupported());
                }
                if size == 18 && format[16..18] != [0, 0] {
                    return Err(unsupported());
                }
            }
            b"data" => {
                if data_seen || !format_seen || size == 0 {
                    return Err(corrupt());
                }
                data_seen = true;
                reader
                    .seek(SeekFrom::Current(size as i64))
                    .map_err(|_| corrupt())?;
            }
            b"LIST" => {
                metadata_bytes += size;
                if metadata_bytes > MAX_TEXT_BYTES {
                    return Err(limit());
                }
                let mut content = vec![0; size];
                read_exact(reader, &mut content)?;
                // INFO can hold title/artist tags; only an encoder-only list is unambiguous here.
                if size < 12 || &content[..4] != b"INFO" || &content[4..8] != b"ISFT" {
                    return Err(unsupported());
                }
                let length =
                    u32::from_le_bytes(content[8..12].try_into().map_err(|_| corrupt())?) as usize;
                if 12 + length + length % 2 != size {
                    return Err(unsupported());
                }
            }
            b"JUNK" | b"PAD " => {
                reader
                    .seek(SeekFrom::Current(size as i64))
                    .map_err(|_| corrupt())?;
            }
            _ => return Err(unsupported()),
        }
        if !size.is_multiple_of(2) {
            reader.seek(SeekFrom::Current(1)).map_err(|_| corrupt())?;
        }
    }
    Err(limit())
}

fn first<'a>(tags: &'a HashMap<String, String>, aliases: &[&str]) -> Option<&'a str> {
    aliases
        .iter()
        .filter_map(|key| tags.get(*key))
        .map(|value| value.trim_matches(python_whitespace))
        .find(|value| !value.is_empty())
}
fn leading_int(value: Option<&str>) -> Option<u32> {
    let digits: String = value?
        .trim_start_matches(python_whitespace)
        .chars()
        .take_while(char::is_ascii_digit)
        .collect();
    if digits.is_empty() {
        return None;
    }
    let significant = digits.trim_start_matches('0');
    if significant.is_empty() {
        Some(0)
    } else {
        significant.chars().take(4).collect::<String>().parse().ok()
    }
}
fn python_whitespace(character: char) -> bool {
    character.is_whitespace() || matches!(character, '\u{1c}'..='\u{1f}')
}
fn year(value: Option<&str>) -> Option<u32> {
    let bytes = value?.as_bytes();
    bytes
        .windows(4)
        .find(|window| window.iter().all(u8::is_ascii_digit))
        .and_then(|window| std::str::from_utf8(window).ok()?.parse().ok())
}
fn metadata(tags: &HashMap<String, String>, duration: f64) -> Value {
    json!({
        "title":first(tags,&["title"]), "artist":first(tags,&["artist","author","performer"]),
        "album":first(tags,&["album"]), "album_artist":first(tags,&["album_artist","albumartist","band"]),
        "track_number":leading_int(first(tags,&["track","tracknumber"])),
        "disc_number":leading_int(first(tags,&["disc","discnumber","disk"])),
        "year":year(first(tags,&["date","year","originalyear","creation_time"])),
        "genre":first(tags,&["genre"]), "duration_seconds":duration
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn pcm() -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(b"RIFF");
        bytes.extend_from_slice(&(36_u32 + 8000).to_le_bytes());
        bytes.extend_from_slice(b"WAVEfmt ");
        bytes.extend_from_slice(&16_u32.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&8000_u32.to_le_bytes());
        bytes.extend_from_slice(&8000_u32.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&8_u16.to_le_bytes());
        bytes.extend_from_slice(b"data");
        bytes.extend_from_slice(&8000_u32.to_le_bytes());
        bytes.resize(8044, 128);
        bytes
    }

    #[test]
    fn wav_layout_accepts_pcm_rejects_truncation_and_disguised_input() {
        let bytes = pcm();
        assert!(scan_wav(&mut Cursor::new(&bytes), bytes.len() as u64).is_ok());
        assert!(scan_wav(&mut Cursor::new(&bytes[..50]), 50).is_err());
        let mut invalid = bytes.clone();
        invalid[20] = 3;
        assert!(scan_wav(&mut Cursor::new(&invalid), invalid.len() as u64).is_err());
    }

    #[test]
    fn mapping_matches_ascii_numeric_and_alias_rules() {
        assert_eq!(leading_int(Some("005/12")), Some(5));
        assert_eq!(leading_int(Some("00000")), Some(0));
        assert_eq!(leading_int(Some("000/12")), Some(0));
        assert_eq!(leading_int(Some("12345/6")), Some(1234));
        assert_eq!(leading_int(Some("-3")), None);
        assert_eq!(year(Some("recorded in 1999")), Some(1999));
        let tags = HashMap::from([
            ("date".into(), "unknown".into()),
            ("year".into(), "2024".into()),
            ("title".into(), "  Padded  ".into()),
        ]);
        let meta = metadata(&tags, 1.0);
        assert_eq!(meta["title"], "Padded");
        assert!(meta["year"].is_null());
    }

    #[test]
    fn text_values_reject_invalid_and_ambiguous_encodings() {
        assert_eq!(decode_text(&[3, b'A', 0]).unwrap(), "A");
        assert_eq!(decode_text(&[1, 0xff, 0xfe, 0xe9, 0]).unwrap(), "é");
        assert!(decode_text(&[3, b'A', 0, b'B']).is_err());
        assert!(decode_text(&[3, 0xff]).is_err());
        assert!(syncsafe(&[0xff, 0, 0, 0]).is_err());
    }

    #[test]
    fn duplicate_tags_are_ambiguous_and_budget_is_cumulative() {
        let mut tags = HashMap::new();
        insert(&mut tags, "title", "A".into()).unwrap();
        assert!(insert(&mut tags, "TITLE", "B".into()).is_err());
        let mut budget = BudgetReader {
            inner: Cursor::new(vec![0; 10]),
            remaining: 3,
        };
        let mut out = [0; 3];
        budget.read_exact(&mut out).unwrap();
        budget.rewind().unwrap();
        assert!(budget.read(&mut out).is_err());
    }

    /// MPEG-1 Layer III stereo frame header followed by a Xing/Info frame.
    fn xing_frame(
        index: &[u8; 4],
        flags: u32,
        frames: u32,
        encoder: &[u8; 4],
        delays: u32,
    ) -> Vec<u8> {
        let mut bytes = vec![0xff, 0xfb, 0x90, 0x00];
        bytes.resize(36, 0);
        bytes.extend_from_slice(index);
        bytes.extend_from_slice(&flags.to_be_bytes());
        if flags & 1 != 0 {
            bytes.extend_from_slice(&frames.to_be_bytes());
        }
        bytes.extend_from_slice(encoder);
        bytes.resize(bytes.len() + 17, 0);
        bytes.extend_from_slice(&delays.to_be_bytes()[1..]);
        bytes.resize(417, 0);
        bytes
    }

    fn duration_of(bytes: &[u8]) -> Result<f64> {
        scan_mp3(&mut Cursor::new(bytes), bytes.len() as u64).map(|layout| layout.duration.unwrap())
    }

    #[test]
    fn mp3_requires_explicit_index_instead_of_vbr_bitrate_estimation() {
        let mut bytes = vec![0; 100];
        bytes[..4].copy_from_slice(&[0xff, 0xfb, 0x90, 0]);
        assert_eq!(
            scan_mp3(&mut Cursor::new(&bytes), 100).unwrap_err().reason,
            "unsupported"
        );
        // VBRI sits at the same offset as Xing but carries a different duration rule.
        bytes[36..40].copy_from_slice(b"VBRI");
        assert_eq!(
            scan_mp3(&mut Cursor::new(&bytes), 100).unwrap_err().reason,
            "unsupported"
        );
        assert!(duration_of(&xing_frame(b"Info", 1, 100, b"LAME", 0)).is_ok());
    }

    #[test]
    fn mp3_duration_follows_the_reference_gapless_rule() {
        // frames * 1152 samples at 44.1 kHz, minus the 12-bit delay and padding of the
        // encoders ffmpeg trusts; the same count untouched for any other encoder.
        let delays = (576 << 12) | 1000;
        let plain = 100.0 * 1152.0 / 44_100.0;
        let trimmed = (100.0 * 1152.0 - 1576.0) / 44_100.0;
        for encoder in [b"LAME", b"Lavf", b"Lavc"] {
            let seconds = duration_of(&xing_frame(b"Xing", 1, 100, encoder, delays)).unwrap();
            assert!((seconds - trimmed).abs() < 1e-9, "{seconds}");
        }
        for encoder in [b"Xing", b"XXXX", b"lame"] {
            let seconds = duration_of(&xing_frame(b"Info", 1, 100, encoder, delays)).unwrap();
            assert!((seconds - plain).abs() < 1e-9, "{seconds}");
        }
    }

    #[test]
    fn mp3_duration_rejects_unreproducible_or_inconsistent_headers() {
        // Without the frame counter ffmpeg estimates from the bitrate: leave it to the oracle.
        assert_eq!(
            duration_of(&xing_frame(b"Xing", 0, 0, b"LAME", 0))
                .unwrap_err()
                .reason,
            "unsupported"
        );
        assert_eq!(
            duration_of(&xing_frame(b"Xing", 1, 0, b"LAME", 0))
                .unwrap_err()
                .reason,
            "unsupported"
        );
        // A trim larger than the whole stream cannot be a valid gapless tag.
        assert_eq!(
            duration_of(&xing_frame(b"Xing", 1, 1, b"LAME", (600 << 12) | 600))
                .unwrap_err()
                .reason,
            "corrupt"
        );
        // Reserved sampling rate.
        let mut reserved = xing_frame(b"Xing", 1, 10, b"LAME", 0);
        reserved[2] |= 0x0c;
        assert_eq!(duration_of(&reserved).unwrap_err().reason, "corrupt");
        // A Xing frame cut before the LAME block is a truncated file, never a guess.
        let short = &xing_frame(b"Xing", 1, 10, b"LAME", 0)[..48];
        assert_eq!(duration_of(short).unwrap_err().reason, "corrupt");
    }
}
