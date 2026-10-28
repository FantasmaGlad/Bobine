#!/usr/bin/env python3
"""Fail on partial signing configuration; only a PR may omit all four secrets."""
import argparse
import os

NAMES = ("ANDROID_KEYSTORE_BASE64", "ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD")


def configured(environment, allow_missing=False):
    present = [name for name in NAMES if environment.get(name, "").strip()]
    if len(present) == len(NAMES):
        return True
    if not present and allow_missing:
        return False
    missing = ", ".join(name for name in NAMES if name not in present)
    raise ValueError(f"Android signing configuration is incomplete; missing: {missing}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()
    try:
        ready = configured(os.environ, args.allow_missing)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    result = f"configured={str(ready).lower()}\n"
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as output:
            output.write(result)
    print(result, end="")
    if not ready:
        print("::warning::Unsigned pull-request validation; release signing was not executed.")


if __name__ == "__main__":
    main()
