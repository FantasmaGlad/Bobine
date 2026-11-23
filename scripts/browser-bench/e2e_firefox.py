#!/usr/bin/env python3
"""Banc de bout en bout Firefox (compatibilité Firefox) : pilote un vrai Firefox (geckodriver) contre une instance Bobine de TEST et vérifie les comportements qui conditionnent le support officiel."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geckodriver_client as wd

BASE = os.environ.get("BOBINE_URL", "http://127.0.0.1:8078").rstrip("/")
HERE = Path(__file__).resolve().parent
MONITOR_JS = (HERE / "monitor.js").read_text(encoding="utf-8")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"[{'OK' if ok else 'ÉCHEC'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def api(path: str, method: str = "GET", body: dict | None = None):
    req = urllib.request.Request(
        f"{BASE}/api{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def ffmpeg_clip(path: Path, codec: str, seconds: int = 3, size: str = "640x360", extra: list[str] | None = None) -> None:
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", str(seconds),
         "-c:v", codec, *(extra or []), "-c:a", "aac", str(path)],
        check=True,
    )


def wait_for(predicate, timeout: float, interval: float = 0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def import_through_ui(paths: list[Path], timeout: float = 120) -> bool:
    wd.navigate(f"{BASE}/library/")
    time.sleep(2)
    wd.execute(MONITOR_JS)
    wd.send_keys(wd.find("input[type=file]"), "\n".join(str(p) for p in paths))
    time.sleep(1)
    wd.execute("Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim().startsWith('Lancer')).click()")
    return bool(wait_for(
        lambda: wd.execute("return /terminé/.test(document.body.innerText) && !/en cours/.test(document.body.innerText)"),
        timeout,
    ))


def resume_after_network_cut(workdir: Path) -> None:
    """Coupe le réseau en plein transfert (proxy limité à 3 Mo/s tué puis relancé) et vérifie que l'envoi reprend sans recommencer ni échouer."""
    from urllib.parse import urlparse

    target_port = urlparse(BASE).port or 80
    big = workdir / "e2e_big.mp4"
    ffmpeg_clip(big, "libx264", seconds=25, size="1920x1080",
                extra=["-preset", "ultrafast", "-b:v", "20M", "-pix_fmt", "yuv420p"])
    size_mb = big.stat().st_size / 1e6
    proxy_cmd = [sys.executable, str(HERE / "throttle_proxy.py"), "3", "10", "8079", str(target_port)]
    proxy = subprocess.Popen(proxy_cmd)
    time.sleep(1)
    try:
        before = len(api("/videos"))
        wd.navigate("http://127.0.0.1:8079/library/")
        time.sleep(3)
        wd.send_keys(wd.find("input[type=file]"), str(big))
        time.sleep(1)
        wd.execute("Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim().startsWith('Lancer')).click()")
        reached = wait_for(lambda: (wd.execute("const m=document.body.innerText.match(/(\\d+)%/);return m?+m[1]:0") or 0) >= 30, 60)
        proxy.kill()
        proxy.wait()
        time.sleep(6)
        proxy = subprocess.Popen(proxy_cmd)
        done = wait_for(lambda: wd.execute("return /terminé/.test(document.body.innerText)"), 180)
        check(f"transfert de {size_mb:.0f} Mo repris après une coupure de 6 s", bool(reached and done) and len(api("/videos")) == before + 1)
    finally:
        proxy.kill()


def check_pages() -> None:
    for route in ("/library/", "/radio/", "/kiosk/?channel=network", "/coach/", "/settings/", "/cinema/"):
        wd.navigate(BASE + route)
        time.sleep(2.5)
        body = wd.execute("return document.body.innerText || ''")
        overlay = wd.execute("return !!document.querySelector('nextjs-portal')")
        check(f"page {route} se charge", len(body) > 20 and not overlay and "Application error" not in body)


def fetch_status(script: str):
    return wd.execute_async("const done=arguments[arguments.length-1];" + script)


def check_api_not_found() -> None:
    wd.navigate(BASE + "/library/")
    time.sleep(1.5)
    head = fetch_status("fetch('/api/videos/999999/stream',{method:'HEAD'}).then(r=>done([r.status,r.headers.get('content-type')]))")
    check("HEAD sur une ressource absente -> 404 non HTML", head[0] == 404 and "html" not in (head[1] or ""), str(head))
    unknown = fetch_status("fetch('/api/inexistant').then(r=>done([r.status,r.headers.get('content-type')]))")
    check("chemin /api inconnu -> 404 non HTML", unknown[0] == 404 and "html" not in (unknown[1] or ""), str(unknown))


def check_chunked_import(workdir: Path) -> None:
    small = workdir / "e2e_h264.mp4"
    mkv = workdir / "e2e_h264.mkv"
    ffmpeg_clip(small, "libx264", extra=["-pix_fmt", "yuv420p"])
    ffmpeg_clip(mkv, "libx264", extra=["-pix_fmt", "yuv420p"])
    before = len(api("/videos"))
    ok = import_through_ui([small, mkv])
    lag = wd.execute("return window.__mon && window.__mon.lagMax")
    check("import MP4 + MKV via le sélecteur (transfert par morceaux)", ok and len(api("/videos")) == before + 2,
          f"{len(api('/videos')) - before} vidéo(s) ajoutée(s)")
    check("réactivité pendant l'import (retard boucle < 200 ms)", lag is not None and lag < 200, f"max {lag} ms")
    chunked = wd.execute(
        "return performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/uploads')).length")
    check("le transfert par morceaux (/api/uploads) a bien été utilisé", chunked and chunked >= 2, f"{chunked} requête(s)")


def check_web_rendition(vid) -> None:
    api(f"/videos/{vid}/web-rendition", "POST")
    ready = wait_for(lambda: api(f"/videos/{vid}")["web_status"] == "ready", 120, 1)
    check("version web produite", bool(ready))
    probe = fetch_status(f"fetch('/api/videos/{vid}/stream?accept=h264',{{method:'HEAD'}}).then(r=>done(r.headers.get('x-bobine-rendition')))")
    check("client sans HEVC -> version web négociée", probe == "web", str(probe))
    played = fetch_status(
        "const v=document.createElement('video');v.muted=true;"
        f"v.src='/api/videos/{vid}/stream?accept=h264';document.body.appendChild(v);"
        "v.play().then(()=>setTimeout(()=>done({t:v.currentTime,err:v.error&&v.error.code,w:v.videoWidth}),2500)).catch(e=>done({err:e.name}))")
    check("la version web se lit dans Firefox", played.get("err") in (None, 0) and played.get("t", 0) > 0.5, str(played))


def check_hevc(workdir: Path) -> None:
    hevc = workdir / "e2e_hevc10.mkv"
    ffmpeg_clip(hevc, "libx265", extra=["-preset", "ultrafast", "-x265-params", "log-level=error", "-pix_fmt", "yuv420p10le"])
    before_ids = {v["id"] for v in api("/videos")}
    import_through_ui([hevc])
    new = [v for v in api("/videos") if v["id"] not in before_ids]
    check("vidéo HEVC 10 bits importée et marquée non lisible partout", bool(new) and not new[0]["web_safe"],
          str(new[0]["web_issues"]) if new else "")
    if new:
        check_web_rendition(new[0]["id"])


def check_cinema_seek_preview() -> None:
    def boards_ready():
        statuses = [fetch_status(f"fetch('/api/videos/{v['id']}/storyboard').then(r=>done(r.status))") for v in api("/videos")]
        return statuses and all(code == 200 for code in statuses)

    check("planches d'aperçu prêtes", bool(wait_for(boards_ready, 120, 2)))
    api("/outputs/cable/mode", "PUT", {"mode": "cinema"})
    wd.navigate(BASE + "/cinema/")
    time.sleep(3)
    wd.execute("document.querySelector('.cinema-hero-play').click()")
    started = wait_for(lambda: wd.execute("const v=document.querySelector('video'); return !!(v && v.readyState >= 1)"), 20, 0.5)
    wd.execute("window.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',keyCode:39,bubbles:true}))")
    time.sleep(0.8)
    shown = wd.execute("return !!document.querySelector('.cinema-controls .seek-preview-image')")
    check("cinéma : un saut à la télécommande affiche l'aperçu de la timeline", bool(started) and shown,
          f"lecture {'lancée' if started else 'non lancée'}, aperçu {'visible' if shown else 'absent'}")


def check_compatibility_section() -> None:
    wd.navigate(BASE + "/settings/#section-playback")
    time.sleep(2.5)
    text = wd.execute("return document.body.innerText")
    check("section « Compatibilité navigateur » affichée", "H.264" in text and "WebSocket" in text)


def start_geckodriver():
    try:
        urllib.request.urlopen(wd.BASE + "/status", timeout=2)
        return None
    except Exception:
        gecko = subprocess.Popen(["geckodriver", "--port", "4444"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        return gecko


def stop(gecko, workdir: Path) -> None:
    try:
        wd.quit_session()
    except Exception:
        pass
    if gecko:
        try:
            gecko.terminate()
        except PermissionError:
            pass
    shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="bobine-e2e-", dir=Path.home()))
    gecko = None
    try:
        gecko = start_geckodriver()
        version = wd.start(headless=True)
        print(f"Firefox {version} — {BASE}")
        check_pages()
        check_api_not_found()
        check_chunked_import(workdir)
        check_hevc(workdir)
        check_cinema_seek_preview()
        if "--resume" in sys.argv:
            resume_after_network_cut(workdir)
        check_compatibility_section()
    finally:
        stop(gecko, workdir)
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} vérifications réussies")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
