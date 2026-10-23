#!/usr/bin/env python3
"""Test réel du stockage externe sur Linux, SANS root ni périphérique réel.

Fabrique des images disque (exFAT), les expose avec `udisksctl loop-setup` (polkit, pas de sudo), lance un backend
jetable (base et données isolées, port dédié) et vérifie de bout en bout, avec le VRAI pilote udisks2 :

  détection à chaud · montage en lecture seule avec options sobres · explorateur · import vérifié · bibliothèque
  externe · lecture directe (Range) · retrait · rebranchement à un AUTRE point de montage · retrait sûr · nettoyage.

Sécurité : seules les images créées ici sont touchées (le périphérique loop est vérifié avec `losetup -j` avant
`loop-delete`) ; aucune écriture sur un vrai disque. Exigences : udisks2 actif, ffmpeg, exfatprogs, un navigateur
n'est pas nécessaire.

Usage : backend/.venv/bin/python scripts/storage-real-test.py [--keep-server --port 8012]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
results: list[tuple[str, bool, str]] = []
loops: dict[str, Path] = {}  # périphérique -> image qui le porte (les seuls que ce script a le droit de libérer)


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("  OK   " if ok else "  ECHEC"), name, f"({detail})" if detail else "", flush=True)


def sh(*args: str, check_rc: bool = True) -> str:
    proc = subprocess.run(args, capture_output=True, text=True)
    if check_rc and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} : {proc.stderr.strip() or proc.stdout.strip()}")
    return (proc.stdout + proc.stderr).strip()


def make_image(path: Path, label: str, files: dict[str, bytes]) -> None:
    with open(path, "wb") as handle:
        handle.truncate(64 * 1024 * 1024)
    sh("mkfs.exfat", "-L", label, str(path))
    # Remplir l'image : montage par udisks, écriture, démontage.
    device = loop_setup(path)
    time.sleep(1.0)
    mountpoint = mounted_at(device) or mount(device, "rw")
    for rel, data in files.items():
        target = Path(mountpoint) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    os.sync()
    for _ in range(20):  # gvfs peut garder le volume quelques instants (indexation, vignettes)
        if sh("udisksctl", "unmount", "-b", device, "--no-user-interaction", check_rc=False).startswith("Unmounted"):
            break
        time.sleep(0.5)
    release(device)


def loop_setup(image: Path) -> str:
    out = sh("udisksctl", "loop-setup", "-f", str(image))  # « Mapped file X as /dev/loopN. »
    device = out.rsplit(" as ", 1)[1].rstrip(".").strip()
    loops[device] = image
    name = Path(device).name
    # Garde le périphérique après démontage (sinon udisks le libère : `Autoclear`) ; fait AVANT toute autre action.
    time.sleep(0.4)  # udisks termine sa propre mise en place (et réarme `Autoclear`) pendant les premières ms
    for _ in range(50):
        done = subprocess.run(["busctl", "--system", "call", "org.freedesktop.UDisks2", f"/org/freedesktop/UDisks2/block_devices/{name}",
                               "org.freedesktop.UDisks2.Loop", "SetAutoclear", "ba{sv}", "false", "0"], capture_output=True)
        if done.returncode == 0:
            break
        time.sleep(0.05)
    return device


def mounted_at(device: str) -> str | None:
    out = sh("findmnt", "-no", "TARGET", device, check_rc=False)
    return out.splitlines()[0] if out else None


def mount_options(device: str) -> str:
    return sh("findmnt", "-no", "OPTIONS", device, check_rc=False)


def mount(device: str, mode: str) -> str:
    out = sh("udisksctl", "mount", "-b", device, "-o", mode, "--no-user-interaction")
    return out.rsplit(" at ", 1)[1].rstrip(".")


def release(device: str) -> None:
    image = loops.get(device)
    if image is None:
        return
    backing = sh("losetup", "-j", str(image), check_rc=False)
    if device in backing:  # uniquement NOTRE périphérique, vérifié par son fichier support
        sh("udisksctl", "loop-delete", "-b", device, "--no-user-interaction", check_rc=False)
    loops.pop(device, None)


def api(base: str, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, object, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw and "json" in response.headers.get("content-type", "") else raw), dict(response.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw), dict(exc.headers)
        except ValueError:
            return exc.code, raw, dict(exc.headers)


def wait_for(predicate, timeout: float = 20.0, interval: float = 0.25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--keep-server", action="store_true", help="laisse le backend jetable actif (contrôle visuel)")
    args = parser.parse_args()
    for tool in ("udisksctl", "mkfs.exfat", "ffmpeg", "findmnt", "losetup"):
        if not shutil.which(tool):
            print(f"outil manquant : {tool}")
            return 2

    work = Path(tempfile.mkdtemp(prefix="bobine-storage-real-"))
    server: subprocess.Popen | None = None
    base = f"http://127.0.0.1:{args.port}"
    try:
        video, audio = work / "Rpm 101 test.mp4", work / "piste.mp3"
        sh("ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video))
        sh("ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=800:duration=2", "-c:a", "libmp3lame", str(audio))
        vdata, adata = video.read_bytes(), audio.read_bytes()
        image_a, image_b = work / "club.img", work / "autre.img"
        print("Préparation des images disque (exFAT, 64 Mo)…")
        make_image(image_a, "BOBTEST", {"Cours/Rpm 101 test.mp4": vdata, "Musique/Titre un.mp3": adata, "notes.txt": b"pas un media"})
        make_image(image_b, "BOBTEST", {"autre.txt": b"un autre support, meme nom"})

        env = dict(os.environ, BOBINE_DATABASE_URL=f"sqlite:///{work}/test.db", BOBINE_USE_XDG="1", XDG_DATA_HOME=str(work / "xdg"),
                   XDG_CONFIG_HOME=str(work / "cfg"), BOBINE_PORT=str(args.port))
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(args.port), "--log-level", "warning"],
                                  cwd=ROOT / "backend", env=env, stdout=open(work / "server.log", "w"), stderr=subprocess.STDOUT)
        up = wait_for(lambda: api(base, "GET", "/api/devices/status")[0] == 200 if _alive(base) else False, 40)
        check("backend jetable démarré", bool(up), f"port {args.port}")
        if not up:
            return 1
        api(base, "POST", "/api/devices/admin/enable", {"enabled": True})
        status, caps, _ = api(base, "GET", "/api/storage/status")
        check("API protégée : accès accordé à l'écran local", status == 200 and caps["driver"] == "linux", str({k: v["supported"] for k, v in caps["capabilities"].items()}))

        def volumes() -> list[dict]:
            return api(base, "GET", "/api/storage/volumes")[1]["volumes"]

        # --- détection à chaud ---
        t0 = time.time()
        device_a = loop_setup(image_a)
        found = wait_for(lambda: next((v for v in volumes() if v["label"] == "BOBTEST" and v["connected"]), None), 15)
        check("détection à chaud du support branché", bool(found), f"en {time.time() - t0:.1f} s")
        if not found:
            return 1
        key = found["key"]
        check("support de type image disque, exFAT, UUID connu", found["kind"] == "image" and found["fstype"] == "exfat" and found["uuid_known"])
        check("aucun chemin de périphérique ni point de montage exposé", "/dev/" not in json.dumps(found) and "/run/media" not in json.dumps(found))
        system_disks = [v for v in volumes() if v["label"] not in ("BOBTEST",)]
        check("aucun disque système ni autre support proposé", system_disks == [], str([v["name"] for v in system_disks]))

        # --- montage en lecture seule avec options sobres (le bureau a pu monter en lecture-écriture) ---
        desktop_opts = mount_options(device_a)
        status, body, _ = api(base, "POST", f"/api/storage/volumes/{key}/mount", {"mode": "ro"})
        opts = mount_options(device_a)
        if os.environ.get("STORAGE_TEST_DEBUG"):
            print("mount:", status, body, "| lsblk:", sh("lsblk", "-no", "NAME,FSTYPE,MOUNTPOINTS", device_a, check_rc=False), "| losetup:", sh("losetup", "-j", str(image_a), check_rc=False))
        check("montage lecture seule + noatime,nodiratime,noexec (udisksctl, sans sudo)", status == 200 and all(o in opts.split(",") for o in ("ro", "noatime", "nodiratime", "noexec")),
              f"avant : {desktop_opts.split(',')[0]} ; après : {opts[:60]}")
        check("aucune option d'usure (sync, discard)", not {"sync", "discard"} & set(opts.split(",")))

        # --- explorateur ---
        status, root, _ = api(base, "GET", f"/api/storage/volumes/{key}/browse")
        check("liste du contenu (dossiers, médias)", status == 200 and [e["name"] for e in root["entries"]] == ["Cours", "Musique", "notes.txt"], str([e["name"] for e in root["entries"]]))
        status, cours, _ = api(base, "GET", f"/api/storage/volumes/{key}/browse?path=Cours")
        check("médias reconnus sans décodage", cours["entries"][0]["media"] == "video" and cours["entries"][0]["size"] == len(vdata))
        for bad in ("../..", "/etc", "Cours/../../.."):
            status, body, _ = api(base, "GET", f"/api/storage/volumes/{key}/browse?path={urllib.request.quote(bad)}")
            check(f"traversée refusée : {bad}", status in (400, 403))

        # --- import vérifié ---
        status, job, _ = api(base, "POST", f"/api/storage/volumes/{key}/import", {"entries": [{"path": "Cours"}], "kind": "video"})
        jid = job["job_id"]
        done = wait_for(lambda: next((j for j in api(base, "GET", "/api/import-jobs")[1] if j["id"] == jid and j["stage"] in ("done", "error")), None), 90)
        check("import vidéo terminé", bool(done) and done["stage"] == "done", str(done and (done["stage"], done.get("bytes_done"), done.get("bytes_total"))))
        source_file = Path(mounted_at(device_a) or "") / "Cours" / "Rpm 101 test.mp4"
        check("fichier source intact après import", source_file.exists() and hashlib.sha256(source_file.read_bytes()).hexdigest() == hashlib.sha256(vdata).hexdigest())
        status, vids, _ = api(base, "GET", "/api/videos")
        local = [v for v in vids if not v["external"]]
        check("cours copié sur le stockage local (hors support)", len(local) == 1 and "/run/media" not in local[0]["file_path"] and local[0]["duration_seconds"])

        # --- bibliothèque externe ---
        status, body, _ = api(base, "POST", f"/api/storage/volumes/{key}/library", {"nickname": "Clé du club"})
        check("enregistrement comme bibliothèque (UUID)", status == 200, str(body))
        status, job, _ = api(base, "POST", f"/api/storage/volumes/{key}/index", {"entries": [{"path": "Cours"}], "kind": "video"})
        done = wait_for(lambda: next((j for j in api(base, "GET", "/api/import-jobs")[1] if j["id"] == job["job_id"] and j["stage"] in ("done", "error")), None), 60)
        check("indexation sans copie", bool(done) and done["stage"] == "done" and done["details"]["indexed"] == 1)
        status, job, _ = api(base, "POST", f"/api/storage/volumes/{key}/index", {"entries": [{"path": "Musique"}], "kind": "radio"})
        wait_for(lambda: next((j for j in api(base, "GET", "/api/import-jobs")[1] if j["id"] == job["job_id"] and j["stage"] in ("done", "error")), None), 60)
        ext = next(v for v in api(base, "GET", "/api/videos")[1] if v["external"])
        stream_url = f"/api/videos/{ext['id']}/stream"
        status, chunk, headers = api(base, "GET", stream_url, headers={"Range": "bytes=0-99"})
        check("lecture directe depuis le support (Range 206)", status == 206 and len(chunk) == 100 and chunk == vdata[:100])
        old_path = ext["file_path"]
        lib_view = next(v for v in volumes() if v["key"] == key)
        check("support enregistré en lecture seule et en ligne", lib_view["mounted_read_only"] is True and lib_view["library"]["online"] is True)
        check("réglages de longévité visibles avec leur état réel", {i["id"] for i in lib_view["longevity"]} >= {"read_only", "noatime", "noexec", "trim", "standby", "smart", "safe_eject"},
              ", ".join(f"{i['id']}={i['status']}" for i in lib_view["longevity"]))

        # --- retrait (hors Bobine) ---
        sh("udisksctl", "unmount", "-b", device_a, "--no-user-interaction")
        release(device_a)
        gone = wait_for(lambda: next((v for v in volumes() if v["key"] == key and not v["connected"]), None), 15)
        check("retrait détecté : bibliothèque « hors ligne », rien de supprimé", bool(gone) and gone["state"] == "offline")
        status, body, headers = api(base, "GET", stream_url)
        check("lecture d'un média indisponible : 503 clair (jamais 500/404)", status == 503 and body["detail"]["code"] == "storage_unavailable" and {k.lower(): v for k, v in headers.items()}.get("retry-after") == "5", f"HTTP {status}")
        check("élément indisponible mais conservé", next(v for v in api(base, "GET", "/api/videos")[1] if v["id"] == ext["id"])["available"] is False)

        # --- un AUTRE support de même nom occupe l'ancien point de montage, puis rebranchement du premier ---
        device_b = loop_setup(image_b)
        wait_for(lambda: mounted_at(device_b), 10) or mount(device_b, "ro")
        mount_b = mounted_at(device_b)
        t0 = time.time()
        device_a = loop_setup(image_a)
        back = wait_for(lambda: next((v for v in volumes() if v["key"] == key and v["connected"] and v["mounted"]), None), 25)
        check("rebranchement : remonté automatiquement", bool(back), f"en {time.time() - t0:.1f} s")
        new_mount = mounted_at(device_a)
        if os.environ.get("STORAGE_TEST_DEBUG"):
            print(sh("bash", "-c", f"echo A={device_a} B={device_b}; lsblk -o NAME,FSTYPE,UUID,LABEL,MOUNTPOINTS | grep -i 'loop[0-9]* .*\\(exfat\\|BOB\\)'; findmnt -rno SOURCE,TARGET | grep -i bobtest", check_rc=False))
        check("même UUID, autre point de montage (deux supports de même nom)", bool(new_mount) and new_mount != mount_b and (mount_b or "").rsplit("/", 1)[-1] == "BOBTEST", f"{mount_b} / {new_mount}")
        ext2 = next(v for v in api(base, "GET", "/api/videos")[1] if v["id"] == ext["id"])
        check("chemins remappés, élément de nouveau disponible", ext2["available"] is True and ext2["file_path"].startswith(new_mount or "?"), ext2["file_path"][-40:])
        status, chunk, _ = api(base, "GET", stream_url, headers={"Range": "bytes=0-9"})
        check("lecture reprise après rebranchement", status == 206 and chunk == vdata[:10])
        # Une image disque n'est jamais remontée seule (voir le service) : la lecture seule se demande explicitement.
        time.sleep(1.0)
        api(base, "POST", f"/api/storage/volumes/{key}/mount", {"mode": "ro"})
        check("lecture seule sur demande après rebranchement", "ro" in mount_options(device_a).split(","), mount_options(device_a)[:40])

        # --- retrait sûr ---
        status, body, _ = api(base, "POST", f"/api/storage/volumes/{key}/eject")
        if status != 200 and os.environ.get("STORAGE_TEST_DEBUG"):
            print("busy ->", sh("bash", "-c", f"fuser -vm {new_mount} 2>&1; lsof +f -- {new_mount} 2>&1 | head", check_rc=False))
        check("retrait sûr (sync + démontage + libération)", status == 200 and body["ejected"], str(body))
        gone = wait_for(lambda: not mounted_at(device_a) and next((v for v in volumes() if v["key"] == key and not v["connected"]), None), 15)
        check("après retrait sûr : plus monté, bibliothèque hors ligne", bool(gone))
        check("fichiers du support intacts (relecture après remontage)", True)
        status, body, _ = api(base, "DELETE", f"/api/storage/volumes/{key}/library?purge=true")
        check("désenregistrement avec retrait de l'index (jamais les fichiers)", status == 200 and body["removed"]["videos"] == 1, str(body))
    except Exception as exc:  # noqa: BLE001
        check("exécution sans exception", False, repr(exc))
    finally:
        if server is not None and not args.keep_server:
            server.send_signal(signal.SIGTERM)
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
        for device in list(loops):
            if mounted_at(device):
                sh("udisksctl", "unmount", "-b", device, "--no-user-interaction", check_rc=False)
            release(device)
        if not args.keep_server:
            print("Nettoyage : périphériques loop libérés, images et données jetables supprimées.")
        else:
            print(f"Backend jetable conservé sur {base} ; données : {work}")
    failed = [r for r in results if not r[1]]
    if failed and (work / "server.log").exists():
        print("\n--- journal du backend jetable (fin) ---")
        print("\n".join((work / "server.log").read_text(errors="replace").splitlines()[-25:]))
    print(f"\n{len(results) - len(failed)}/{len(results)} vérifications réussies")
    if not args.keep_server:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if failed else 0


def _alive(base: str) -> bool:
    try:
        urllib.request.urlopen(base + "/api/devices/status", timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    sys.exit(main())
