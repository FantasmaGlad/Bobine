"""Optional synchronous transport for the audio metadata component.

The singleton owns one child and serializes callers from import worker threads.
It is deliberately disconnected from the importers until native parity is proven.
All failures request the historical media path; no media or database is changed.
"""
from __future__ import annotations

import atexit
import base64
import binascii
from dataclasses import dataclass, field
import json
import logging
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from typing import Any, Sequence

logger = logging.getLogger(__name__)
PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_COVER_BYTES = 4 * 1024 * 1024
PROFILES = frozenset(("radio-v1", "course-duration-v1"))
_METADATA_KEYS = frozenset(("title", "artist", "album", "album_artist", "track_number", "disc_number", "year", "genre", "duration_seconds"))
_NATIVE_REASONS = frozenset(("not_found", "unreadable", "unsupported", "corrupt", "limit_exceeded", "ambiguous_metadata", "ambiguous_cover"))


class _Failure(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class _NativeFailure(_Failure):
    pass


@dataclass(frozen=True)
class CoverResult:
    """available=True and data=None means a proven absence, not a failure."""
    available: bool
    data: bytes | None = None
    mime: str | None = None


@dataclass
class _Generation:
    proc: subprocess.Popen
    replies: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1))
    stop: threading.Event = field(default_factory=threading.Event)
    shutdown_lock: threading.Lock = field(default_factory=threading.Lock)
    threads: list[threading.Thread] = field(default_factory=list)
    formats: frozenset[str] = field(default_factory=frozenset)


def _valid_path(path: os.PathLike | str) -> str | None:
    try:
        value = os.fspath(path)
        if not isinstance(value, str) or not value or "\0" in value:
            return None
        value.encode("utf-8", "strict")
        value.encode(sys.getfilesystemencoding(), "strict")
        return value
    except (TypeError, ValueError, UnicodeError):
        return None


def find_binary() -> list[str] | None:
    """Overrides are single executable paths, never shell command strings."""
    suffix = ".exe" if os.name == "nt" else ""
    candidates: list[Path] = []
    for name in ("BOBINE_MEDIA_SIDECAR", "BOBINE_MEDIA_BIN"):
        override = os.environ.get(name)
        if override:
            valid = _valid_path(override)
            if valid is None:
                return None
            # An explicit but invalid override must not silently select another binary.
            candidate = Path(valid)
            return [str(candidate)] if candidate.is_file() and os.access(candidate, os.X_OK) else None
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates.extend((executable_dir / f"bobine-media{suffix}", executable_dir.parent / "Resources" / f"bobine-media{suffix}"))
    else:
        candidates.append(Path(__file__).resolve().parents[3] / "media" / "target" / "release" / f"bobine-media{suffix}")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return [str(candidate)]
    return None


def _child_env() -> dict[str, str]:
    # Keep this transport independent of the update orchestration imports.
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original:
            env["LD_LIBRARY_PATH"] = original
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _Failure("timeout")
    return remaining


def _publish(generation: _Generation, value: bytes | _Failure) -> bool:
    if generation.stop.is_set():
        return False
    try:
        generation.replies.put_nowait(value)
        return True
    except queue.Full:
        # Unsolicited output cannot allocate an unbounded response queue.
        try:
            generation.replies.get_nowait()
        except queue.Empty:
            pass
        try:
            generation.replies.put_nowait(_Failure("protocol"))
        except queue.Full:
            pass
        return False


def _read_replies(generation: _Generation) -> None:
    proc = generation.proc
    assert proc.stdout is not None
    pending = bytearray()
    try:
        while not generation.stop.is_set():
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                _publish(generation, _Failure("eof"))
                return
            for part_index, part in enumerate(chunk.split(b"\n")):
                if part_index:
                    # The final CR of CRLF is framing, not part of the payload limit.
                    raw = bytes(pending[:-1] if pending.endswith(b"\r") else pending)
                    pending.clear()
                    if len(raw) > MAX_RESPONSE_BYTES or not _publish(generation, raw):
                        if len(raw) > MAX_RESPONSE_BYTES:
                            _publish(generation, _Failure("response_limit"))
                        return
                if len(pending) + len(part) > MAX_RESPONSE_BYTES + 1:
                    _publish(generation, _Failure("response_limit"))
                    return
                pending.extend(part)
    except (OSError, ValueError):
        _publish(generation, _Failure("io"))


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _Failure("protocol")
        result[key] = value
    return result


def _validate_json(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise _Failure("protocol")
    if isinstance(value, str):
        value.encode("utf-8", "strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            key.encode("utf-8", "strict")
            _validate_json(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json(item)


class MediaClient:
    """Thread-safe, lazy client; close is final for this instance.

    A per-generation bounded reader queue prevents an old process from delivering
    late replies to its replacement. Pipe workers also work on Windows, where
    select() cannot wait on anonymous subprocess pipes.
    """
    def __init__(self, command: Sequence[str] | None = None, *, timeout: float = 5.0, enabled: bool | None = None):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self._command = list(command) if command is not None else None
        self.timeout = timeout
        self._enabled = enabled
        self._serial = threading.Lock()
        self._state = threading.Lock()
        self._generation: _Generation | None = None
        self._closed = False
        self._next_id = 0
        self.last_failure: str | None = None

    def _shutdown(self, generation: _Generation, *, graceful: bool = False) -> None:
        with generation.shutdown_lock:
            # Wake a caller blocked on replies before stopping the reader.
            _publish(generation, _Failure("closed"))
            generation.stop.set()
            proc = generation.proc
            if graceful and proc.poll() is None and proc.stdin is not None:
                proc.stdin.close()
                try:
                    proc.wait(timeout=0.15)
                except subprocess.TimeoutExpired:
                    pass
            if proc.poll() is None:
                proc.kill()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                # A pathological OS-level uninterruptible wait is not a successful reap.
                logger.warning("Audio metadata component did not exit after kill")
                return
            for stream in (proc.stdin, proc.stdout):
                if stream is not None:
                    stream.close()
            for thread in tuple(generation.threads):
                if thread is not threading.current_thread():
                    thread.join(timeout=0.1)

    def _detach(self, generation: _Generation) -> None:
        with self._state:
            if self._generation is generation:
                self._generation = None
        self._shutdown(generation)

    def close(self) -> None:
        with self._state:
            self._closed = True
            generation, self._generation = self._generation, None
        if generation is not None:
            self._shutdown(generation, graceful=True)

    def _spawn(self, deadline: float) -> _Generation:
        command = self._command if self._command is not None else find_binary()
        if not command:
            raise _Failure("missing")
        _remaining(deadline)
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, bufsize=0, shell=False,
                                close_fds=True, env=_child_env(),
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        generation = _Generation(proc)
        with self._state:
            closed = self._closed
            if not closed:
                self._generation = generation
        if closed:
            self._shutdown(generation)
            raise _Failure("closed")
        reader = threading.Thread(target=_read_replies, args=(generation,), daemon=True, name="bobine-media-reader")
        generation.threads.append(reader)
        reader.start()
        _remaining(deadline)
        try:
            generation.formats = self._hello(self._exchange(generation, "hello", {}, deadline))
        except _NativeFailure as exc:
            # A business refusal before identification never authorizes reuse.
            raise _Failure("handshake") from exc
        return generation

    def _exchange(self, generation: _Generation, method: str, params: dict, deadline: float) -> dict:
        _remaining(deadline)
        self._next_id += 1
        if self._next_id > 2**53 - 1:
            raise _Failure("protocol")
        request_id = self._next_id
        raw = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_REQUEST_BYTES:
            raise _Failure("request_limit")
        written: queue.Queue = queue.Queue(maxsize=1)

        def write() -> None:
            try:
                assert generation.proc.stdin is not None
                view = memoryview(raw + b"\n")
                while view:
                    count = generation.proc.stdin.write(view)
                    if not count:
                        raise OSError("closed pipe")
                    view = view[count:]
                written.put_nowait(True)
            except (OSError, ValueError):
                written.put_nowait(_Failure("io"))

        writer = threading.Thread(target=write, daemon=True, name="bobine-media-writer")
        generation.threads.append(writer)
        writer.start()
        try:
            status = written.get(timeout=_remaining(deadline))
            if isinstance(status, _Failure):
                raise status
            reply = generation.replies.get(timeout=_remaining(deadline))
        except queue.Empty as exc:
            raise _Failure("timeout") from exc
        finally:
            # Keep only active workers rather than one Thread object per imported song.
            generation.threads[:] = [thread for thread in generation.threads if thread.is_alive()]
        if isinstance(reply, _Failure):
            raise reply
        _remaining(deadline)
        try:
            message = json.loads(reply.decode("utf-8", "strict"), object_pairs_hook=_pairs)
            _validate_json(message)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise _Failure("protocol") from exc
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or type(message.get("id")) is not int or message["id"] != request_id:
            raise _Failure("protocol")
        if ("result" in message) == ("error" in message):
            raise _Failure("protocol")
        if "error" in message:
            error = message["error"]
            if not isinstance(error, dict) or type(error.get("code")) is not int or not isinstance(error.get("message"), str):
                raise _Failure("protocol")
            data = error.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("reason"), str):
                raise _Failure("protocol")
            reason = data["reason"]
            raise _NativeFailure(reason if reason in _NATIVE_REASONS else "native_error")
        if not isinstance(message["result"], dict):
            raise _Failure("protocol")
        if method == "probe_audio" and (not isinstance(message["result"].get("format"), str) or message["result"]["format"] not in generation.formats):
            raise _Failure("protocol")
        return message["result"]

    @staticmethod
    def _hello(result: dict) -> frozenset[str]:
        limits = result.get("limits")
        capabilities = result.get("capabilities")
        profiles, formats = result.get("profiles"), result.get("formats")
        if (type(result.get("protocol_version")) is not int or result["protocol_version"] != PROTOCOL_VERSION
                or not isinstance(result.get("binary_version"), str) or not result["binary_version"]
                or not isinstance(profiles, list) or any(not isinstance(item, str) for item in profiles) or not PROFILES.issubset(profiles)
                or not isinstance(formats, list) or not formats or any(not isinstance(item, str) or not item for item in formats)
                or not isinstance(capabilities, dict) or any(capabilities.get(key) is not True for key in ("probe_audio", "extract_cover", "experimental"))
                or not isinstance(limits, dict)
                or any(type(limits.get(key)) is not int or limits[key] != expected for key, expected in (("request_bytes", MAX_REQUEST_BYTES), ("response_bytes", MAX_RESPONSE_BYTES), ("cover_bytes", MAX_COVER_BYTES)))):
            raise _Failure("handshake")
        return frozenset(formats)

    def _call(self, method: str, path: os.PathLike | str, profile: str | None, validate):
        if (self._enabled if self._enabled is not None else os.environ.get("BOBINE_MEDIA_NATIVE") == "1") is not True:
            self.last_failure = "disabled"
            return None
        valid = _valid_path(path)
        if valid is None:
            self.last_failure = "path"
            return None
        deadline = time.monotonic() + self.timeout
        if not self._serial.acquire(timeout=max(0.0, deadline - time.monotonic())):
            self.last_failure = "timeout"
            return None
        generation = None
        try:
            with self._state:
                if self._closed:
                    raise _Failure("closed")
                generation = self._generation
            if generation is not None and generation.proc.poll() is not None:
                self._detach(generation)
                generation = None
            if generation is None:
                generation = self._spawn(deadline)
            params = {"path": valid}
            if profile is not None:
                params["profile"] = profile
            result = validate(self._exchange(generation, method, params, deadline))
            _remaining(deadline)
            self.last_failure = None
            return result
        except _NativeFailure as exc:
            self.last_failure = exc.reason
            logger.info("Audio metadata fallback: %s", exc.reason)
            return None
        except (OSError, ValueError, _Failure) as exc:
            reason = exc.reason if isinstance(exc, _Failure) else "io"
            self.last_failure = reason
            logger.info("Audio metadata fallback: %s", reason)
            # Spawn may fail after assigning its generation but before returning it.
            if generation is None:
                with self._state:
                    generation = self._generation
            if generation is not None:
                self._detach(generation)
            return None
        finally:
            self._serial.release()

    def probe_audio(self, path: os.PathLike | str, profile: str = "radio-v1") -> dict | None:
        if not isinstance(profile, str) or profile not in PROFILES:
            self.last_failure = "profile"
            return None

        def validate(result: dict) -> dict:
            metadata = result.get("metadata")
            if result.get("status") != "ok" or result.get("profile") != profile or not isinstance(result.get("format"), str) or not result["format"] or not isinstance(metadata, dict) or set(metadata) != _METADATA_KEYS:
                raise _Failure("protocol")
            for key in ("title", "artist", "album", "album_artist", "genre"):
                if metadata[key] is not None and not isinstance(metadata[key], str):
                    raise _Failure("protocol")
            for key in ("track_number", "disc_number", "year"):
                if metadata[key] is not None and (type(metadata[key]) is not int or metadata[key] < 0):
                    raise _Failure("protocol")
            duration = metadata["duration_seconds"]
            if duration is not None and (type(duration) not in (int, float) or duration < 0 or duration > sys.float_info.max or not math.isfinite(duration)):
                raise _Failure("protocol")
            return dict(metadata)

        return self._call("probe_audio", path, profile, validate)

    def extract_cover(self, path: os.PathLike | str) -> CoverResult:
        def validate(result: dict) -> CoverResult:
            if result.get("status") != "ok" or "cover" not in result:
                raise _Failure("protocol")
            cover = result["cover"]
            if cover is None:
                return CoverResult(available=True)
            if not isinstance(cover, dict) or cover.get("mime") not in ("image/jpeg", "image/png") or type(cover.get("bytes")) is not int or not 0 < cover["bytes"] <= MAX_COVER_BYTES or not isinstance(cover.get("data_base64"), str):
                raise _Failure("protocol")
            encoded = cover["data_base64"]
            if len(encoded) != 4 * ((cover["bytes"] + 2) // 3):
                raise _Failure("protocol")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise _Failure("protocol") from exc
            if len(data) != cover["bytes"] or base64.b64encode(data).decode("ascii") != encoded:
                raise _Failure("protocol")
            return CoverResult(available=True, data=data, mime=cover["mime"])

        result = self._call("extract_cover", path, "radio-v1", validate)
        return result if result is not None else CoverResult(available=False)


_singleton: MediaClient | None = None
_singleton_lock = threading.Lock()


def get_media_client() -> MediaClient:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = MediaClient()
            atexit.register(_singleton.close)
        return _singleton


def close_current_media_client() -> None:
    """Stop an existing owner at backend shutdown without constructing a client."""
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            _singleton.close()
            _singleton = None
