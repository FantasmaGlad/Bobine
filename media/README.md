# bobine-media (experimental)

A read-only audio inspector. It is a standalone prototype and is not enabled in the application. It does not open a network port, spawn a shell, decode audio, modify media or access a database. The existing ffprobe/ffmpeg path remains necessary for unsupported inputs and images.

Build and check with `cargo test --locked`, `cargo clippy --all-targets -- -D warnings`, and `cargo build --release --locked`. Run `target/release/bobine-media`; send one JSON-RPC object per UTF-8 line on stdin. Responses are JSON only on stdout; EOF exits. A final line without a newline is accepted. Diagnostics never include input paths. Detailed protocol: [PROTOCOL.md](PROTOCOL.md).

## Experimental subset

- MP3: MPEG Layer III with an explicit Xing/Info index, starting directly after an optional ID3v2.3/2.4 tag. Only unique, unflagged fixed text frames for title/artist/album/album artist/track/disc/date/genre and encoder are accepted. Standard Latin-1/UTF-8/UTF-16 text is read without replacement. Missing Xing/Info, a Xing/Info frame without a frame counter, VBRI, ID3v1/APE, custom frames, multiple tag values, ambiguous dates, numeric genre mappings and other layouts return an explicit fallback error. Missing-index VBR showed a substantial duration difference in development comparison and is deliberately excluded. Duration follows the reference rule rather than Lofty's raw frame count: `frames x samples-per-frame / sample rate`, minus the 12-bit encoder delay and padding when the Xing/Info frame names LAME, Lavf or Lavc (any other encoder string keeps the raw count). Lofty's value must agree within 0.4 s or the file falls back; on 602 generated files the native and ffprobe durations differ by less than a microsecond, whereas the raw count over-reported by up to 52 ms.
- FLAC: mandatory STREAMINFO, optional padding/seek table and one bounded Vorbis comment block with a limited set of known fields. Duplicate keys, arbitrary application/cue blocks, embedded ID3 or nonstandard image comments require fallback.
- WAV: little-endian RIFF PCM with one `fmt ` and one `data` chunk, optional encoder-only INFO and padding. Other metadata, extensible/float/RF64 layouts require fallback.
- `extract_cover` proves absence only for these subsets. Every embedded image returns `ambiguous_cover`; JPEG/PNG byte transport is reserved for later image parity work. A first APIC cannot be assumed equivalent to ffmpeg's default stream selection or its intermediate JPEG conversion.

The whitelist describes parser eligibility, not production certification of every file with these extensions. Compare every accepted file with the reference oracle before enabling any profile. `radio-v1` and `course-duration-v1` remain distinct profiles; their current equal result for these simple single-audio layouts must not be generalized to other containers. Filename-derived titles and ordering remain the caller's responsibility.

## Resource and lifecycle limits

Initial limits are experimental: request 64 KiB, response 8 MiB (both excluding LF/CRLF), cover 4 MiB, media file 512 MiB, aggregate metadata 4 MiB, text block 64 KiB, metadata/chunk count 128, Vorbis items 256 and cumulative physical reads 16 MiB per request. Oversized request frames are discarded without allocating a full line, followed by a structured error. The parser does not decode images.

Lofty is pinned to 0.22.4. Its per-thread `GlobalOptions::allocation_limit` is set to 4 MiB before each parse, custom resolvers and format-specific preservation are disabled, strict parsing is selected, and tag/image allocation is avoided with `read_tags(false)`/`read_cover_art(false)` after bounded preflight inspection. This is not a hard process RSS cap. Byte limits do not substitute for a future image pixel limit.

The crate uses the repository's AGPL-3.0-or-later license. Lofty, Serde and serde_json are MIT OR Apache-2.0; locked transitive dependencies also provide permissive license choices (including Unicode-3.0 and zlib notices). Preserve their license notices when distributing binaries. Cargo.lock fixes the exact dependency graph.

Only absolute Unicode paths to regular local files are accepted; symbolic links and special files are rejected. Path normalization and replacement characters are never applied. POSIX non-UTF-8 paths cannot be represented by this protocol and must use the reference path. This executable is an internal subprocess, not a filesystem security boundary: the caller must supply trusted local paths and prevent hostile concurrent replacement. Metadata is checked before/after inspection to detect ordinary source changes.

The caller owns startup, serialization, deadlines, cancellation and process collection. Suggested development deadlines are 2 seconds for `hello` and 5 seconds for an inspection; these are caller policies, not timers implemented inside the parser. EOF stops the process between requests. A parent dying during a blocked filesystem operation is not guaranteed to terminate an active request; the supervisor must handle that case before distribution.

No hardware profile is certified by the native unit tests. Android/Bionic packaging and lifecycle, Windows process flags and Unicode, macOS signing, and Linux/appliance packages require separate validation.
