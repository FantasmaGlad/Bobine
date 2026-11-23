import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HASH = {".py", ".sh", ".yml", ".yaml", ".toml", ".ps1", ".install", ".rpmlintrc", ".rules", ".service", ".in"}
SLASH = {".ts", ".tsx", ".js", ".mjs", ".kt", ".kts", ".rs"}
THIRD_PARTY = ("android/gradlew", "frontend/public/", "Assets/")


def _is_comment(suffix: str, line: str, first: bool) -> bool:
    text = line.strip()
    if suffix in SLASH:
        return text.startswith(("//", "/*", "*")) and "eslint-" not in text and "@ts-" not in text
    if suffix == ".iss":
        return text.startswith(";")
    if suffix == ".xml":
        return text.startswith("<!--") and "-->" not in text
    return text.startswith("# ") and not first


def _tracked() -> list[str]:
    listing = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True)
    return [name for name in listing.stdout.splitlines() if not name.startswith(THIRD_PARTY)]


def test_no_comment_spans_more_than_one_line():
    blocks = []
    for name in _tracked():
        path = REPO / name
        suffix = path.suffix if path.suffix else (".sh" if name.startswith(("packaging/", "scripts/")) else "")
        if suffix not in HASH | SLASH | {".iss", ".xml"}:
            continue
        previous = False
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            current = _is_comment(suffix, line, number == 1)
            if current and (previous or suffix == ".xml"):
                blocks.append(f"{name}:{number}")
            previous = current
    assert blocks == []


NO_COMMENT_FILES = (".gitignore", ".gitattributes")
NO_COMMENT_PREFIXES = ("backend/requirements", "backend/constraints")
ACCENTED = set("àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ")
TEXT_TEMPLATES = ("scripts/ci/render-rolling-notes.py",)


def _comment_lines(name: str):
    path = REPO / name
    suffix = path.suffix if path.suffix else (".sh" if name.startswith(("packaging/", "scripts/")) else "")
    if suffix not in HASH | SLASH | {".iss"}:
        return
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if _is_comment(suffix, line, number == 1) and not line.strip().startswith(("#!", "#[")):
            yield number, line.strip()


def test_ignore_and_requirement_files_have_no_comment():
    found = []
    for name in _tracked():
        if Path(name).name in NO_COMMENT_FILES or name.startswith(NO_COMMENT_PREFIXES) or name.endswith(".iss"):
            lines = (REPO / name).read_text(encoding="utf-8").splitlines()
            marker = ";" if name.endswith(".iss") else "#"
            found += [f"{name}:{n}" for n, line in enumerate(lines, 1) if line.lstrip().startswith(marker)]
    assert found == []


def test_kept_comments_are_one_technical_line_in_english():
    names = [name for name in _tracked() if not name.startswith(TEXT_TEMPLATES)]
    french = [f"{name}:{number}" for name in names for number, text in _comment_lines(name) or () if ACCENTED & set(text)]
    assert french == []
