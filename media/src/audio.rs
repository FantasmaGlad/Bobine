//! Shared parts of the container readers, and the entry point that selects one.
//!
//! Every container reader is a strict whitelist: it understands one layout, reproduces
//! the tags and the duration ffprobe reports for it, and answers `unsupported`,
//! `ambiguous_metadata` or `ambiguous_cover` for anything else so that the caller runs
//! the reference path. A reader never guesses.

use crate::image;
use crate::{aiff, flac, mp3, mp4, ogg, wav, MediaError};
use lofty::config::{apply_global_options, GlobalOptions, ParseOptions, ParsingMode};
use lofty::file::{AudioFile, FileType};
use lofty::probe::Probe;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs::File;
use std::io::{self, BufReader, Read, Seek, SeekFrom};
use std::path::Path;

pub(crate) const MAX_FILE_BYTES: u64 = 512 * 1024 * 1024;
pub(crate) const MAX_METADATA_BYTES: usize = 4 * 1024 * 1024;
pub(crate) const MAX_TEXT_BYTES: usize = 64 * 1024;
const MAX_READ_BYTES: usize = 16 * 1024 * 1024;
/// A file whose frames are walked end to end (MP3 without an index) may be read once in full.
pub(crate) const MAX_CHAIN_BYTES: u64 = 128 * 1024 * 1024;
/// Delay and padding are 12-bit sample counts: 2 x 4095 samples at 22.05 kHz at most.
const MAX_GAPLESS_TRIM_SECONDS: f64 = 0.4;

pub(crate) type Result<T> = std::result::Result<T, MediaError>;

pub(crate) fn corrupt() -> MediaError {
    MediaError::new("corrupt", "Invalid or truncated audio data")
}
pub(crate) fn unsupported() -> MediaError {
    MediaError::new(
        "unsupported",
        "Audio layout is outside the experimental subset",
    )
}
pub(crate) fn ambiguous() -> MediaError {
    MediaError::new(
        "ambiguous_metadata",
        "Metadata cannot be mapped without ambiguity",
    )
}
pub(crate) fn ambiguous_cover() -> MediaError {
    MediaError::new(
        "ambiguous_cover",
        "Embedded images require the reference image pipeline",
    )
}
/// A picture that cannot be handed over keeps its reference pipeline, unless a size limit
/// is what stopped the inspection.
pub(crate) fn cover_error(error: MediaError) -> MediaError {
    if error.reason == "limit_exceeded" {
        error
    } else {
        ambiguous_cover()
    }
}
pub(crate) fn limit() -> MediaError {
    MediaError::new("limit_exceeded", "Media inspection limit exceeded")
}
pub(crate) fn read_exact(reader: &mut impl Read, bytes: &mut [u8]) -> Result<()> {
    reader.read_exact(bytes).map_err(|error| {
        if error.kind() == io::ErrorKind::Other {
            limit()
        } else {
            corrupt()
        }
    })
}

/// How the duration of a scanned file is obtained.
#[derive(Default, Debug, Clone, Copy, PartialEq)]
pub(crate) enum Duration {
    /// Lofty's reading is equivalent to the reference (FLAC, simple PCM WAV).
    #[default]
    Lofty,
    /// The reference rule computed by this crate, which Lofty's raw reading must bracket.
    Checked(f64),
    /// The reference rule computed by this crate, verified against ffprobe on the corpus.
    Exact(f64),
}

/// A picture announced by the container: the type it declares, if any, and its bytes.
#[derive(Debug)]
pub(crate) struct Picture {
    pub declared: Option<String>,
    pub data: Vec<u8>,
}

#[derive(Default, Debug)]
pub(crate) struct Layout {
    pub tags: HashMap<String, String>,
    /// Number of attached pictures. Only one is eligible for the native cover path.
    pub pictures: usize,
    /// The first picture, kept only when the reader was asked for it.
    pub picture: Option<Picture>,
    pub duration: Duration,
}

impl Layout {
    pub(crate) fn add_picture(
        &mut self,
        want: bool,
        picture: impl FnOnce() -> Result<Picture>,
    ) -> Result<()> {
        self.pictures += 1;
        if want && self.pictures == 1 {
            self.picture = Some(picture()?);
        }
        Ok(())
    }
}

/// A cumulative read budget supplements Lofty's per-item allocation bound.
pub(crate) struct BudgetReader<R> {
    pub(crate) inner: R,
    pub(crate) remaining: usize,
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

#[derive(Clone, Copy, PartialEq)]
enum Kind {
    Mp3,
    Flac,
    Wav,
    Mp4,
    Ogg,
    Aiff,
}

impl Kind {
    fn of(extension: &str) -> Option<Self> {
        Some(match extension {
            "mp3" => Self::Mp3,
            "flac" => Self::Flac,
            "wav" => Self::Wav,
            "m4a" => Self::Mp4,
            "ogg" | "opus" => Self::Ogg,
            "aiff" | "aif" => Self::Aiff,
            _ => return None,
        })
    }
    fn lofty(self) -> Option<FileType> {
        match self {
            Self::Mp3 => Some(FileType::Mpeg),
            Self::Flac => Some(FileType::Flac),
            Self::Wav => Some(FileType::Wav),
            _ => None,
        }
    }
}

pub(crate) const FORMATS: [&str; 8] = ["mp3", "flac", "wav", "m4a", "ogg", "opus", "aiff", "aif"];

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
    let kind = Kind::of(&format).ok_or_else(unsupported)?;
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
    let chain = if kind == Kind::Mp3 && opened.len() <= MAX_CHAIN_BYTES {
        opened.len() as usize
    } else {
        0
    };
    let mut reader = BufReader::new(BudgetReader {
        inner: file,
        remaining: MAX_READ_BYTES + chain,
    });
    let length = opened.len();
    let layout = match kind {
        Kind::Mp3 => mp3::scan(&mut reader, length, cover_only)?,
        Kind::Flac => flac::scan(&mut reader, length, cover_only)?,
        Kind::Wav => wav::scan(&mut reader, length)?,
        Kind::Mp4 => mp4::scan(&mut reader, length, cover_only)?,
        Kind::Ogg => ogg::scan(&mut reader, length, cover_only)?,
        Kind::Aiff => aiff::scan(&mut reader, length)?,
    };
    let duration = match (layout.duration, kind.lofty()) {
        (Duration::Exact(seconds), _) => positive(seconds)?,
        (Duration::Checked(reference), Some(file_type)) => {
            let parsed = lofty_duration(&mut reader, file_type)?;
            // The reference (ffprobe) removes the encoder delay and padding announced in the
            // LAME tag; Lofty reports the raw frame count. Two independent readings must agree
            // within the largest plausible trim before the reference rule is trusted.
            if !reference.is_finite() || reference <= 0.0 {
                return Err(corrupt());
            }
            if parsed - reference < -0.001 || parsed - reference > MAX_GAPLESS_TRIM_SECONDS {
                return Err(ambiguous());
            }
            reference
        }
        (Duration::Lofty, Some(file_type)) => lofty_duration(&mut reader, file_type)?,
        _ => return Err(unsupported()),
    };
    let after = reader.get_ref().inner.metadata().map_err(|_| corrupt())?;
    if after.len() != opened.len() || after.modified().ok() != opened.modified().ok() {
        return Err(MediaError::new(
            "unreadable",
            "Media changed during inspection",
        ));
    }
    if cover_only {
        return Ok(json!({"status":"ok","cover":cover(&layout)?}));
    }
    Ok(
        json!({"status":"ok","profile":profile,"format":format,"metadata":metadata(&layout.tags, duration)}),
    )
}

fn positive(seconds: f64) -> Result<f64> {
    if seconds.is_finite() && seconds > 0.0 {
        Ok(seconds)
    } else {
        Err(corrupt())
    }
}

fn lofty_duration(reader: &mut BufReader<BudgetReader<File>>, file_type: FileType) -> Result<f64> {
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
    let tagged = Probe::with_file_type(&mut *reader, file_type)
        .options(options)
        .read()
        .map_err(|_| {
            if reader.get_ref().remaining == 0 {
                limit()
            } else {
                corrupt()
            }
        })?;
    positive(tagged.properties().duration().as_secs_f64())
}

/// `null` is a proven absence; one structurally accepted picture is handed over as raw bytes.
fn cover(layout: &Layout) -> Result<Value> {
    match (layout.pictures, &layout.picture) {
        (0, _) => Ok(Value::Null),
        (1, Some(picture)) => {
            let mime = image::classify(&picture.data, picture.declared.as_deref())?;
            Ok(
                json!({"mime":mime,"bytes":picture.data.len(),"data_base64":image::base64_encode(&picture.data)}),
            )
        }
        _ => Err(ambiguous_cover()),
    }
}

pub(crate) fn insert(tags: &mut HashMap<String, String>, key: &str, value: String) -> Result<()> {
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

    #[test]
    fn cover_is_absent_single_or_refused() {
        let jpeg = {
            let mut bytes = vec![0xff, 0xd8, 0xff, 0xc0, 0, 11, 8, 0, 4, 0, 4, 1, 1, 0x11, 0];
            bytes.extend_from_slice(&[0xff, 0xda, 0, 2, 0xff, 0xd9]);
            bytes
        };
        let mut layout = Layout::default();
        assert!(cover(&layout).unwrap().is_null());
        layout
            .add_picture(true, || {
                Ok(Picture {
                    declared: Some("image/jpeg".into()),
                    data: jpeg.clone(),
                })
            })
            .unwrap();
        let value = cover(&layout).unwrap();
        assert_eq!(value["mime"], "image/jpeg");
        assert_eq!(value["bytes"], jpeg.len());
        layout.add_picture(true, || unreachable!()).unwrap();
        assert_eq!(cover(&layout).unwrap_err().reason, "ambiguous_cover");
    }
}
