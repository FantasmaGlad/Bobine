import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
THIRD_PARTY = ("android/gradlew", "frontend/public/", "Assets/")
SELF = "backend/tests/test_code_policy.py"
CODE = re.compile(r"\.(py|[cm]?[jt]sx?|rs|kts?|sh|bash|ya?ml|toml|ps1)$|^install\.sh$")
PYTHON_JS = re.compile(r"\.(py|[cm]?[jt]sx?)$")
JS = re.compile(r"\.[cm]?[jt]sx?$")
EXECUTED = re.compile(r"\.(sh|bash|ya?ml|ps1)$|^install\.sh$")
TESTS = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*\.py$|\.(test|spec)\.[cm]?[jt]sx?$|Test\.kt$")
RULES = {
    "processus par interpréteur de commandes": (re.compile(r"shell\s*=\s*True|\bos\.system\(|\bos\.popen\("), CODE),
    "eval, exec ou new Function": (re.compile(r"(?<![\w.])(eval|exec)\(|\bnew Function\("), PYTHON_JS),
    "désérialisation non sûre": (re.compile(r"\b(pickle|marshal)\.loads?\(|\byaml\.load\((?![^)]*Loader)|\byaml\.unsafe_load\("), CODE),
    "vérification TLS désactivée": (re.compile(r"verify\s*=\s*False|check_hostname\s*=\s*False|rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED|--insecure\b|curl\s+[^\n]*\s-k\b"), CODE),
    "fichier temporaire prévisible": (re.compile(r"\btempfile\.mktemp\("), CODE),
    "SQL construit par chaîne": (re.compile(r"\b(text|execute|executemany)\(\s*f[\"']"), CODE),
    "droits 777": (re.compile(r"\bchmod\s+(-R\s+)?0?777\b"), CODE),
    "script téléchargé exécuté sans vérification": (re.compile(r"\b(curl|wget)\b[^|\n]*\|\s*(sudo\s+)?(ba|z)?sh\b"), EXECUTED),
    "dérogation globale": (re.compile(r"#\s*noqa(?!:)|#\s*type:\s*ignore(?!\[)|@ts-ignore|eslint-disable(-next-line|-line)?\s*(\*/)?\s*$|#!\[allow\(warnings\)\]"), CODE),
    "test neutralisé": (re.compile(r"@pytest\.mark\.skip\b(?!if)|pytest\.mark\.xfail|@unittest\.skip\(|expectedFailure|@pytest\.mark\.flaky|reruns\s*=|\b(describe|it|test)\.(only|skip|todo)\(|\{\s*skip\s*:\s*true|@Ignore\b|#\[ignore\]"), TESTS),
}
HTML_SINK = re.compile(r"dangerouslySetInnerHTML|\.(inner|outer)HTML\s*=")
HTML_CONSTANT = re.compile(r"__html:\s*(JSON\.stringify\(|[`'\"]|[A-Z][A-Z0-9_]+\b)|\.(inner|outer)HTML\s*=\s*(['\"])[^'\"]*\3\s*;?\s*$")
HTML_VARIABLE = re.compile(r"__html:\s*`[^`]*\$\{(?![A-Z][A-Z0-9_]*\})")
EXCEPTIONS = {
    ("SQL construit par chaîne", "backend/app/database/foreign_keys.py"): "PRAGMA et DDL sur des identifiants du schéma passés par _quote",
    ("SQL construit par chaîne", "backend/app/database/migrations.py"): "DDL sur les noms de tables et de colonnes du modèle",
    ("SQL construit par chaîne", "backend/tests/test_foreign_keys.py"): "PRAGMA sur un nom de table du modèle",
    ("eval, exec ou new Function", "backend/tests/test_channel_icons_wiring.py"): "préambule d'un fichier .spec PyInstaller du dépôt",
    ("HTML injecté hors constante", "frontend/src/components/InlineScript.tsx"): "ne reçoit que des constantes, vérifié par test_inline_script_receives_constants",
}


def _tracked() -> list[str]:
    listing = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True)
    return [name for name in listing.stdout.splitlines() if CODE.search(name) and not name.startswith(THIRD_PARTY) and name != SELF]


def _findings(name: str, lines: list[str]) -> set[str]:
    found = set()
    for index, line in enumerate(lines):
        if re.match(r"\s*-?\s*name:", line) and name.endswith((".yml", ".yaml")):
            continue
        for rule, (pattern, scope) in RULES.items():
            if scope.search(name) and pattern.search(line):
                found.add(rule)
        if JS.search(name) and HTML_SINK.search(line):
            window = " ".join(lines[index:index + 3])
            if not HTML_CONSTANT.search(window) or HTML_VARIABLE.search(window):
                found.add("HTML injecté hors constante")
        if name.endswith(".rs") and re.search(r"\bunsafe\s*(\{|fn\b|impl\b)", line) and "SAFETY" not in " ".join(lines[max(index - 1, 0):index + 1]):
            found.add("unsafe sans SAFETY")
    return found


def test_no_banned_construct_outside_documented_exceptions():
    found = {}
    for name in _tracked():
        lines = (REPO / name).read_text(encoding="utf-8", errors="ignore").splitlines()
        for rule in _findings(name, lines):
            found[(rule, name)] = True
    assert sorted(key for key in found if key not in EXCEPTIONS) == []
    assert sorted(key for key in EXCEPTIONS if key not in found) == []


def test_inline_script_receives_constants():
    calls = subprocess.run(["git", "grep", "-h", "-o", r"<InlineScript [^>]*>", "--", "frontend/src"], cwd=REPO, capture_output=True, text=True, check=True)
    values = re.findall(r"html=\{([^}]*)\}", calls.stdout)
    assert values and all(re.fullmatch(r"[A-Z][A-Z0-9_]+", value) for value in values)
