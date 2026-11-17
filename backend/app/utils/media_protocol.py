"""Couche fil du composant média : trames JSON-RPC, lecture des réponses, échecs typés."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
import queue
import subprocess
import threading
import time
from typing import Any

MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_NATIVE_REASONS = frozenset(("not_found", "unreadable", "unsupported", "corrupt", "limit_exceeded", "ambiguous_metadata", "ambiguous_cover"))


class Failure(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class NativeFailure(Failure):
    pass


@dataclass
class Generation:
    proc: subprocess.Popen
    replies: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1))
    stop: threading.Event = field(default_factory=threading.Event)
    shutdown_lock: threading.Lock = field(default_factory=threading.Lock)
    threads: list[threading.Thread] = field(default_factory=list)
    formats: frozenset[str] = field(default_factory=frozenset)
    version: str = ""


def remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise Failure("timeout")
    return remaining


def publish(generation: Generation, value: bytes | Failure) -> bool:
    if generation.stop.is_set():
        return False
    try:
        generation.replies.put_nowait(value)
        return True
    except queue.Full:
        try:
            generation.replies.get_nowait()
        except queue.Empty:
            pass
        try:
            generation.replies.put_nowait(Failure("protocol"))
        except queue.Full:
            pass
        return False


def read_replies(generation: Generation) -> None:
    proc = generation.proc
    assert proc.stdout is not None
    pending = bytearray()
    try:
        while not generation.stop.is_set():
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                publish(generation, Failure("eof"))
                return
            for part_index, part in enumerate(chunk.split(b"\n")):
                if part_index:
                    raw = bytes(pending[:-1] if pending.endswith(b"\r") else pending)
                    pending.clear()
                    if len(raw) > MAX_RESPONSE_BYTES or not publish(generation, raw):
                        if len(raw) > MAX_RESPONSE_BYTES:
                            publish(generation, Failure("response_limit"))
                        return
                if len(pending) + len(part) > MAX_RESPONSE_BYTES + 1:
                    publish(generation, Failure("response_limit"))
                    return
                pending.extend(part)
    except (OSError, ValueError):
        publish(generation, Failure("io"))


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise Failure("protocol")
        result[key] = value
    return result


def _validate_json(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise Failure("protocol")
    if isinstance(value, str):
        value.encode("utf-8", "strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            key.encode("utf-8", "strict")
            _validate_json(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json(item)


def encode_request(request_id: int, method: str, params: dict) -> bytes:
    raw = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_REQUEST_BYTES:
        raise Failure("request_limit")
    return raw


def _write_request(generation: Generation, raw: bytes, written: queue.Queue) -> None:
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
        written.put_nowait(Failure("io"))


def send(generation: Generation, raw: bytes, deadline: float):
    written: queue.Queue = queue.Queue(maxsize=1)
    writer = threading.Thread(target=_write_request, args=(generation, raw, written), daemon=True, name="bobine-media-writer")
    generation.threads.append(writer)
    writer.start()
    try:
        status = written.get(timeout=remaining(deadline))
        if isinstance(status, Failure):
            raise status
        reply = generation.replies.get(timeout=remaining(deadline))
    except queue.Empty as exc:
        raise Failure("timeout") from exc
    finally:
        generation.threads[:] = [thread for thread in generation.threads if thread.is_alive()]
    if isinstance(reply, Failure):
        raise reply
    return reply


def _native_error(error) -> NativeFailure:
    if not isinstance(error, dict) or type(error.get("code")) is not int or not isinstance(error.get("message"), str):
        raise Failure("protocol")
    data = error.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("reason"), str):
        raise Failure("protocol")
    reason = data["reason"]
    return NativeFailure(reason if reason in _NATIVE_REASONS else "native_error")


def decode_reply(reply: bytes, request_id: int) -> dict:
    try:
        message = json.loads(reply.decode("utf-8", "strict"), object_pairs_hook=_pairs)
        _validate_json(message)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Failure("protocol") from exc
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or type(message.get("id")) is not int or message["id"] != request_id:
        raise Failure("protocol")
    if ("result" in message) == ("error" in message):
        raise Failure("protocol")
    if "error" in message:
        raise _native_error(message["error"])
    if not isinstance(message["result"], dict):
        raise Failure("protocol")
    return message["result"]
