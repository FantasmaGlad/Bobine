#!/usr/bin/env python3
"""Resolve one unambiguous release intent and derive native package versions."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("release_channel_build", ROOT / "backend/app/release_channel.py")
registry = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = registry
SPEC.loader.exec_module(registry)


def resolve(base, event, ref, tag="", beta=False, canary=False, run="1", commit="aaaaaaa"):
    if not re.fullmatch(r"\d+\.\d+\.\d+", base):
        raise ValueError("VERSION must contain a base x.y.z version")
    if event not in ("push", "pull_request", "workflow_dispatch"):
        raise ValueError("Unsupported workflow event")
    if sum((bool(tag), beta, canary)) > 1:
        raise ValueError("tag, publish_beta and publish_canary are mutually exclusive")
    if event != "workflow_dispatch" and (tag or beta or canary):
        raise ValueError("Manual release inputs require workflow_dispatch")
    if not re.fullmatch(r"[a-f0-9]{7,40}", commit):
        raise ValueError("Invalid build revision")
    channel, tag_name = "none", ""
    ref_tag = ref.removeprefix("refs/tags/") if ref.startswith("refs/tags/") else ""
    if ref_tag and (beta or canary):
        raise ValueError("Rolling publication must select a branch, not a Stable tag")
    if tag and ref_tag and tag != ref_tag:
        raise ValueError("Requested tag differs from the workflow reference")
    stable_tag = tag or ref_tag
    if stable_tag:
        if not re.fullmatch(r"V\d+\.\d+\.\d+", stable_tag):
            raise ValueError("Stable tags must be Vx.y.z, without pre-release iteration suffixes")
        if stable_tag[1:] != base:
            raise ValueError("Stable tag differs from VERSION")
        channel, tag_name = "stable", stable_tag
    elif beta or canary:
        channel = "beta" if beta else "canary"
        tag_name = registry.get(channel).release_tag
    elif event == "push" and ref == "refs/heads/main":
        channel, tag_name = "canary", registry.get("canary").release_tag
    rolling = channel in registry.ROLLING_CHANNEL_IDS
    package = registry.package_version(base, channel if channel != "none" else "stable", run if rolling else None)
    return {
        "channel": channel, "tag_name": tag_name, "base_version": base,
        "display_version": f"{base}-{channel}" if rolling else base,
        "deb_version": package.debian,
        "filename_version": channel if rolling else base,
        "commit_short": commit,
    }


def main():
    values = []
    for key in ("RELEASE_BETA", "RELEASE_CANARY"):
        value = os.environ.get(key, "false") or "false"
        if value not in ("true", "false"):
            raise ValueError(f"{key} must be true or false")
        values.append(value == "true")
    result = resolve(
        (ROOT / "VERSION").read_text().strip(), os.environ["GITHUB_EVENT_NAME"], os.environ["GITHUB_REF"],
        os.environ.get("RELEASE_TAG", ""), *values, os.environ["GITHUB_RUN_NUMBER"],
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip(),
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        for key, value in result.items():
            output.write(f"{key}={value}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Release resolution failed: {exc}") from exc
