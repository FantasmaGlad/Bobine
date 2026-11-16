"""Exécution de commandes système sans shell pour les pilotes Linux."""

from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable

from ..base import DeviceError

CommandResult = tuple[int, str, str]
Runner = Callable[..., Awaitable[CommandResult]]


async def run_command(*args: str, timeout: float = 10.0, stdin: str | None = None) -> CommandResult:
    """Exécute une commande sans shell, avec délai d'expiration et environnement stable (`LC_ALL=C`)."""
    env = dict(os.environ, LC_ALL="C", LANG="C")
    runtime_dir = f"/run/user/{os.getuid()}" if hasattr(os, "getuid") else ""
    if not env.get("XDG_RUNTIME_DIR") and runtime_dir and os.path.isdir(runtime_dir):
        env["XDG_RUNTIME_DIR"] = runtime_dir
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as exc:
        raise DeviceError("tool_missing", f"Outil système introuvable : {args[0]}", 501) from exc
    except OSError as exc:
        raise DeviceError("tool_failed", f"Impossible de lancer {args[0]} : {exc.strerror or exc}", 502) from exc
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(stdin.encode() if stdin is not None else None), timeout=timeout
        )
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.communicate()
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise DeviceError("timeout", f"{args[0]} n'a pas répondu dans le délai imparti.", 504) from exc
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")
