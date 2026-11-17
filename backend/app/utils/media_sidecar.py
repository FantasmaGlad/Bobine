"""Optional synchronous transport for the audio metadata component."""
from __future__ import annotations

import atexit
import base64
import binascii
from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Sequence

from app.utils import media_native
from app.utils.media_protocol import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    Failure,
    Generation,
    NativeFailure,
    decode_reply,
    encode_request,
    publish,
    read_replies,
    remaining,
    send,
)

logger = logging.getLogger(__name__)
PROTOCOL_VERSION = 1
MAX_COVER_BYTES = 4 * 1024 * 1024
PROFILES = frozenset(("radio-v1", "course-duration-v1"))
_METADATA_KEYS = frozenset(("title", "artist", "album", "album_artist", "track_number", "disc_number", "year", "genre", "duration_seconds"))


@dataclass(frozen=True)
class CoverResult:
    """available=True and data=None means a proven absence, not a failure."""
    available: bool
    data: bytes | None = None
    mime: str | None = None


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
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original:
            env["LD_LIBRARY_PATH"] = original
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


class MediaClient:
    """Thread-safe, lazy client; close is final for this instance."""
    def __init__(self, command: Sequence[str] | None = None, *, timeout: float = 5.0, enabled: bool | None = None):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self._command = list(command) if command is not None else None
        self.timeout = timeout
        self._enabled = enabled
        self._serial = threading.Lock()
        self._state = threading.Lock()
        self._generation: Generation | None = None
        self._closed = False
        self._next_id = 0
        self.last_failure: str | None = None

    def _shutdown(self, generation: Generation, *, graceful: bool = False) -> None:
        with generation.shutdown_lock:
            publish(generation, Failure("closed"))
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
                logger.warning("Audio metadata component did not exit after kill")
                return
            for stream in (proc.stdin, proc.stdout):
                if stream is not None:
                    stream.close()
            for thread in tuple(generation.threads):
                if thread is not threading.current_thread():
                    thread.join(timeout=0.1)

    def _detach(self, generation: Generation) -> None:
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

    def _spawn(self, deadline: float) -> Generation:
        command = self._command if self._command is not None else find_binary()
        if not command:
            raise Failure("missing")
        remaining(deadline)
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, bufsize=0, shell=False,
                                close_fds=True, env=_child_env(),
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        generation = Generation(proc)
        with self._state:
            closed = self._closed
            if not closed:
                self._generation = generation
        if closed:
            self._shutdown(generation)
            raise Failure("closed")
        reader = threading.Thread(target=read_replies, args=(generation,), daemon=True, name="bobine-media-reader")
        generation.threads.append(reader)
        reader.start()
        remaining(deadline)
        try:
            hello = self._exchange(generation, "hello", {}, deadline)
            generation.formats = self._hello(hello)
            generation.version = hello["binary_version"]
        except NativeFailure as exc:
            raise Failure("handshake") from exc
        return generation

    def _exchange(self, generation: Generation, method: str, params: dict, deadline: float) -> dict:
        remaining(deadline)
        self._next_id += 1
        if self._next_id > 2**53 - 1:
            raise Failure("protocol")
        request_id = self._next_id
        reply = send(generation, encode_request(request_id, method, params), deadline)
        remaining(deadline)
        result = decode_reply(reply, request_id)
        if method == "probe_audio" and (not isinstance(result.get("format"), str) or result["format"] not in generation.formats):
            raise Failure("protocol")
        return result

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
            raise Failure("handshake")
        return frozenset(formats)

    def _is_enabled(self) -> bool:
        return (self._enabled if self._enabled is not None else media_native.is_enabled()) is True

    def _run(self, action):
        deadline = time.monotonic() + self.timeout
        if not self._serial.acquire(timeout=max(0.0, deadline - time.monotonic())):
            self.last_failure = "timeout"
            return None
        generation = None
        try:
            with self._state:
                if self._closed:
                    raise Failure("closed")
                generation = self._generation
            if generation is not None and generation.proc.poll() is not None:
                self._detach(generation)
                generation = None
            if generation is None:
                generation = self._spawn(deadline)
            result = action(generation, deadline)
            remaining(deadline)
            self.last_failure = None
            return result
        except NativeFailure as exc:
            self.last_failure = exc.reason
            logger.info("Audio metadata fallback: %s", exc.reason)
            return None
        except (OSError, ValueError, Failure) as exc:
            reason = exc.reason if isinstance(exc, Failure) else "io"
            self.last_failure = reason
            logger.info("Audio metadata fallback: %s", reason)
            if generation is None:
                with self._state:
                    generation = self._generation
            if generation is not None:
                self._detach(generation)
            return None
        finally:
            self._serial.release()

    def _call(self, method: str, path: os.PathLike | str, profile: str | None, validate):
        if not self._is_enabled():
            self.last_failure = "disabled"
            return None
        valid = _valid_path(path)
        if valid is None:
            self.last_failure = "path"
            return None

        def action(generation: Generation, deadline: float):
            params = {"path": valid}
            if profile is not None:
                params["profile"] = profile
            return validate(self._exchange(generation, method, params, deadline))

        return self._run(action)

    def check(self) -> dict | None:
        """Start the component if needed and report what it announced, or None."""
        if not self._is_enabled():
            self.last_failure = "disabled"
            return None
        return self._run(lambda generation, _deadline: {"binary_version": generation.version, "formats": sorted(generation.formats)})

    def probe_audio(self, path: os.PathLike | str, profile: str = "radio-v1") -> dict | None:
        if not isinstance(profile, str) or profile not in PROFILES:
            self.last_failure = "profile"
            return None

        def validate(result: dict) -> dict:
            metadata = result.get("metadata")
            if result.get("status") != "ok" or result.get("profile") != profile or not isinstance(result.get("format"), str) or not result["format"] or not isinstance(metadata, dict) or set(metadata) != _METADATA_KEYS:
                raise Failure("protocol")
            for key in ("title", "artist", "album", "album_artist", "genre"):
                if metadata[key] is not None and not isinstance(metadata[key], str):
                    raise Failure("protocol")
            for key in ("track_number", "disc_number", "year"):
                if metadata[key] is not None and (type(metadata[key]) is not int or metadata[key] < 0):
                    raise Failure("protocol")
            duration = metadata["duration_seconds"]
            if duration is not None and (type(duration) not in (int, float) or duration < 0 or duration > sys.float_info.max or not math.isfinite(duration)):
                raise Failure("protocol")
            return dict(metadata)

        return self._call("probe_audio", path, profile, validate)

    def extract_cover(self, path: os.PathLike | str) -> CoverResult:
        def validate(result: dict) -> CoverResult:
            if result.get("status") != "ok" or "cover" not in result:
                raise Failure("protocol")
            cover = result["cover"]
            if cover is None:
                return CoverResult(available=True)
            if not isinstance(cover, dict) or cover.get("mime") not in ("image/jpeg", "image/png") or type(cover.get("bytes")) is not int or not 0 < cover["bytes"] <= MAX_COVER_BYTES or not isinstance(cover.get("data_base64"), str):
                raise Failure("protocol")
            encoded = cover["data_base64"]
            if len(encoded) != 4 * ((cover["bytes"] + 2) // 3):
                raise Failure("protocol")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise Failure("protocol") from exc
            if len(data) != cover["bytes"] or base64.b64encode(data).decode("ascii") != encoded:
                raise Failure("protocol")
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


