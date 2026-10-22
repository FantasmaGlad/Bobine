# Media protocol version 1

Each message is one UTF-8 JSON object on a line, up to the advertised byte limit excluding the final LF or CRLF. A request has exactly `jsonrpc`, `id`, `method`, and optional `params`. `jsonrpc` must be `"2.0"`; `id` is an integer from 1 through 9007199254740991. Batch requests and notifications are rejected. Duplicate envelope/parameter fields, unknown fields and invalid JSON values are rejected. Every response contains `jsonrpc`, `id`, and exactly one of `result` or `error`. Invalid requests use `id:null`.

## Identification

Request:

```json
{"jsonrpc":"2.0","id":1,"method":"hello","params":{}}
```

Result:

```json
{"protocol_version":1,"binary_version":"0.1.0","profiles":["radio-v1","course-duration-v1"],"formats":["mp3","flac","wav","m4a","ogg","opus","aiff","aif"],"capabilities":{"probe_audio":true,"extract_cover":true,"experimental":true},"limits":{"request_bytes":65536,"response_bytes":8388608,"cover_bytes":4194304}}
```

Capabilities mean that methods exist for the documented experimental subset. They do not imply production certification. `formats` lists the file extensions the executable may answer for; a given file of such an extension can still be outside the subset. Unsupported layouts always return errors.

## Audio inspection

```json
{"jsonrpc":"2.0","id":2,"method":"probe_audio","params":{"path":"/corpus/01_intro.mp3","profile":"radio-v1"}}
```

A successful `result` has exactly this shape:

```json
{"status":"ok","profile":"radio-v1","format":"mp3","metadata":{"title":null,"artist":null,"album":null,"album_artist":null,"track_number":null,"disc_number":null,"year":null,"genre":null,"duration_seconds":1.37}}
```

`format` is the lowercase file extension, one of the advertised `formats`; `profile` echoes the accepted profile. The nine metadata keys are always present, including for `course-duration-v1`. Text and integer values can be null; duration is a positive finite number in seconds, equal to what ffprobe reports for the same file (MP3 encoder delay and padding included in that rule, see the README). The caller consumes only duration for the course profile and retains its historical filename parsing. A null native title means no title tag, so the radio caller must apply its filename fallback. There is no mutation or filename parsing in this executable.

## Image inspection

```json
{"jsonrpc":"2.0","id":3,"method":"extract_cover","params":{"path":"/corpus/01_intro.mp3","profile":"radio-v1"}}
```

A supported file with no image returns `{"status":"ok","cover":null}` (a proven absence). A file with exactly one embedded picture that is structurally inside the accepted families returns `{"status":"ok","cover":{"mime":"image/jpeg","bytes":N,"data_base64":"..."}}`: the raw embedded bytes, never decoded or re-encoded by the executable (`mime` is `image/jpeg` or `image/png`, `bytes` at most `cover_bytes`, standard padded Base64). The accepted families are 8-bit JPEG (baseline, extended or progressive; 1 or 3 components; upright, with no Adobe marker) and non-interlaced 8-bit PNG without animation or EXIF; the MIME type the container declares must agree with the bytes; at most 40 million pixels. Anything else (several pictures, another format, CMYK, a rotated EXIF orientation, 16-bit or interlaced PNG, a declared type that contradicts the bytes) returns `ambiguous_cover` and the caller uses the reference pipeline. Image normalization and JPEG output remain the caller's responsibility; the cover equivalence the caller relies on is defined in the README.

## Errors

```json
{"jsonrpc":"2.0","id":2,"error":{"code":-32001,"message":"Audio layout is outside the experimental subset","data":{"reason":"unsupported"}}}
```

Standard JSON-RPC codes: `-32700` parse error, `-32600` invalid envelope, `-32601` unknown method, `-32602` invalid parameters. Media errors use `-32001` with stable `data.reason`: `not_found`, `unreadable`, `unsupported`, `corrupt`, `limit_exceeded`, `ambiguous_metadata` or `ambiguous_cover`. Messages contain no source paths. Errors never mean successful empty metadata or a missing image. A caller must execute the reference path or surface cancellation as appropriate.

For an oversized line, the entire frame is discarded up to LF or EOF before returning `limit_exceeded` with `id:null`; the next frame is independent. Syntax errors also leave the line protocol synchronized. Inspection requests are processed sequentially. EOF with no buffered message produces no response and exits successfully.
