from app import cli


REPORT = {"status": "warning", "checks": [], "problems": [
    {"code": "import_job_stuck", "severity": "warning", "message": "bloqué", "remedy": "annuler",
     "fix": {"action": "cancel_import_jobs", "job_ids": ["abcdef0123456789"]}},
    {"code": "media_native_fallback", "severity": "info", "message": "inutilisé", "remedy": "désactiver",
     "fix": {"action": "set_settings", "settings": {"media_native": "false"}}},
    {"code": "firewall_rule_missing", "severity": "warning", "message": "règle absente", "remedy": "à la main"},
]}


def _scripted(monkeypatch, calls):
    answers = {"n": 0}

    def request(self, method, path, **kw):
        calls.append((method, path, kw.get("body")))
        if (method, path) == ("GET", "/api/diagnostics/system"):
            answers["n"] += 1
            return REPORT if answers["n"] == 1 else {"status": "warning", "checks": [], "problems": [REPORT["problems"][2]]}
        return {}

    monkeypatch.setattr(cli.Client, "request", request)


def test_auto_fix_without_yes_only_lists(monkeypatch, capsys):
    calls = []
    _scripted(monkeypatch, calls)
    assert cli.main(["--port", "1903", "diagnose", "--auto-fix"]) == cli.EXIT_ERROR
    out = capsys.readouterr().out
    assert "2 correction(s) possible(s)" in out and "--yes" in out
    assert [c for c in calls if c[0] != "GET"] == []


def test_auto_fix_yes_applies_only_the_declared_fixes(monkeypatch, capsys):
    calls = []
    _scripted(monkeypatch, calls)
    cli.main(["--port", "1903", "diagnose", "--auto-fix", "--yes"])
    writes = [c for c in calls if c[0] != "GET"]
    assert writes == [("DELETE", "/api/import-jobs/abcdef0123456789", None), ("PUT", "/api/settings", {"media_native": "false"})]
    out = capsys.readouterr().out
    assert "corrigé : import_job_stuck : import abcdef01 annulé" in out and "1 constat(s) restant(s)" in out


def test_diagnose_without_the_option_changes_nothing(monkeypatch):
    calls = []
    _scripted(monkeypatch, calls)
    cli.main(["--port", "1903", "diagnose"])
    assert [c for c in calls if c[0] != "GET"] == []


def test_unknown_fix_is_an_error_not_a_crash(monkeypatch, capsys):
    monkeypatch.setattr(cli.Client, "request", lambda self, m, p, **kw: {"status": "warning", "checks": [], "problems": [
        {"code": "x", "severity": "info", "message": "m", "remedy": "r", "fix": {"action": "inconnue"}}]})
    assert cli.main(["--port", "1903", "diagnose", "--auto-fix", "--yes"]) == cli.EXIT_ERROR
    assert "correction inconnue" in capsys.readouterr().err
