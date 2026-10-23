#!/usr/bin/env python3
"""Test réel de l'assistant de formatage, SANS root et sur IMAGE DISQUE uniquement (jamais un vrai périphérique).

Fabrique une image disque exFAT, l'expose avec `udisksctl loop-setup` (polkit, pas de sudo) et lance un backend jetable dont
le formatage est restreint par construction à CE seul périphérique loop (variable BOBINE_STORAGE_FORMAT_ONLY) : même un défaut de
Bobine ne pourrait pas écrire ailleurs. Vérifie avec le VRAI pilote udisks2 (D-Bus) :

  plan sans écriture · refus d'un support enregistré (puis désenregistrement) · dérive d'identité (un autre support apparaît)
  · jeton à usage unique · formatage exFAT rapide (GPT, alignement 1 Mio, cluster adapté, aucun écrasement complet) ·
  vérification après coup (type, étiquette, UUID nouveau, lecture seule, fichier de test) · reformatage ext4 (sans blocs réservés,
  propriété du compte) · nettoyage complet.

Sécurité : les vrais supports amovibles branchés sur le poste (ex. une clé USB) sont seulement LUS par `lsblk` pour constater,
à la fin, qu'aucun n'a changé ; ils ne sont jamais montés, écrits ni formatés. Exigences : udisks2 actif, exfatprogs, e2fsprogs.
Avec --authorize-image, une autorisation sudo déjà ouverte installe une règle polkit temporaire
limitée au seul loop créé, puis la retire ; aucun privilège sur les vrais supports.

Usage : backend/.venv/bin/python scripts/storage-format-real-test.py [--port 8013]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("storage_real", HERE / "storage-real-test.py")
real = importlib.util.module_from_spec(_spec)
sys.modules["storage_real"] = real
_spec.loader.exec_module(real)  # type: ignore[union-attr]

check, sh, api, wait_for = real.check, real.sh, real.api, real.wait_for
GIB = 1024 ** 3


def lsblk_state() -> dict[str, dict]:
    """Photographie en LECTURE SEULE de tous les disques : identité, table, partitions, montages."""
    out = sh("lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,SERIAL,MODEL,PTTYPE,TYPE,UUID,FSTYPE,LABEL,MOUNTPOINTS,RM,TRAN", check_rc=False)
    try:
        data = json.loads(out)
    except ValueError:
        return {}
    state: dict[str, dict] = {}
    for node in data.get("blockdevices", []):
        if node.get("type") == "loop":
            continue
        children = [(c.get("path"), c.get("uuid"), c.get("fstype"), c.get("label"), c.get("size"), tuple(m for m in (c.get("mountpoints") or []) if m)) for c in node.get("children", []) or []]
        state[node["path"]] = {"size": node.get("size"), "serial": node.get("serial"), "pttype": node.get("pttype"), "children": children,
                               "fs": (node.get("uuid"), node.get("fstype"), node.get("label"))}
    return state


def block_info(device: str) -> dict:
    out = sh("lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,PTTYPE,TYPE,UUID,FSTYPE,LABEL,START,MOUNTPOINTS,PARTTYPENAME", device, check_rc=False)
    try:
        node = json.loads(out)["blockdevices"][0]
    except (ValueError, KeyError, IndexError):
        return {"pttype": None, "parts": [], "gone": True}
    return {"pttype": node.get("pttype"), "parts": node.get("children") or []}


class KeepAlive(threading.Thread):
    """Désarme `Autoclear` du périphérique loop de CE test, sur évènement D-Bus et en boucle rapide : udisks le réarme après un
    formatage, et un démontage libérerait alors l'image (propre aux images de test, sans objet pour une vraie clé)."""

    def __init__(self, device: str):
        super().__init__(daemon=True)
        self.path = f"/org/freedesktop/UDisks2/block_devices/{Path(device).name}"
        self.stop_flag = threading.Event()

    def run(self) -> None:
        import asyncio

        from dbus_fast import BusType, Message, MessageType
        from dbus_fast.aio import MessageBus

        async def disarm(bus) -> None:
            await bus.call(Message(destination="org.freedesktop.UDisks2", path=self.path, interface="org.freedesktop.UDisks2.Loop",
                                   member="SetAutoclear", signature="ba{sv}", body=[False, {}]))

        async def main() -> None:
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            loop = asyncio.get_running_loop()

            def on_message(message) -> None:
                if message.message_type == MessageType.SIGNAL and message.member == "PropertiesChanged" and message.path == self.path and message.body[1].get("Autoclear") and message.body[1]["Autoclear"].value is True:
                    loop.create_task(disarm(bus))

            bus.add_message_handler(on_message)
            await bus.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus", interface="org.freedesktop.DBus", member="AddMatch",
                                   signature="s", body=[f"type='signal',sender='org.freedesktop.UDisks2',interface='org.freedesktop.DBus.Properties',path='{self.path}'"]))
            while not self.stop_flag.is_set():
                try:
                    await disarm(bus)
                except Exception:  # noqa: BLE001 - périphérique momentanément absent
                    pass
                await asyncio.sleep(0.02)
            bus.disconnect()

        asyncio.run(main())


def teardown(device: str) -> None:
    """Démonte (le bureau monte tout seul les images qui apparaissent) puis libère un périphérique loop de CE test."""
    for _ in range(12):
        mounted = [p for p in sh("lsblk", "-nlo", "PATH", device, check_rc=False).splitlines() if real.mounted_at(p.strip())]
        if not mounted:
            break
        for path in mounted:
            sh("udisksctl", "unmount", "-b", path.strip(), "--no-user-interaction", check_rc=False)
        time.sleep(0.5)
    real.release(device)


def allocated_kib(image: Path) -> int:
    return int(sh("du", "-k", str(image)).split()[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8013)
    parser.add_argument("--authorize-image", action="store_true", help="règle polkit temporaire limitée au loop créé (sudo préalablement autorisé)")
    args = parser.parse_args()
    for tool in ("udisksctl", "mkfs.exfat", "mkfs.ext4", "findmnt", "losetup", "busctl", "lsblk", "du"):
        if not shutil.which(tool):
            print(f"outil manquant : {tool}")
            return 2

    work = Path(tempfile.mkdtemp(prefix="bobine-format-real-"))
    server: subprocess.Popen | None = None
    keep: KeepAlive | None = None
    base = f"http://127.0.0.1:{args.port}"
    test_policy = None
    other_device = None
    before = lsblk_state()
    try:
        suffix = os.urandom(2).hex().upper()
        label_a = f"BFMT{suffix}"
        image = work / "support.img"
        other = work / "autre.img"
        print("Préparation de l'image disque (exFAT, 1 Gio creux) avec du contenu…")
        with open(image, "wb") as handle:
            handle.truncate(GIB)
        sh("mkfs.exfat", "-L", label_a, str(image))
        device = real.loop_setup(image)
        if args.authorize_image:
            if not device.startswith("/dev/loop") or not Path(f"/sys/class/block/{Path(device).name}/loop/backing_file").read_text().strip().endswith(str(image)):
                raise RuntimeError("Le support de test ne correspond pas à l'image créée.")
            import re
            test_policy = "/etc/polkit-1/rules.d/00-bobine-format-test.rules"
            policy_source = work / "test.rules"
            pattern = "^" + re.escape(device) + "(p[0-9]+)?$"
            policy_source.write_text('polkit.addRule(function(a,s) { if (s.user === ' + json.dumps(__import__("getpass").getuser()) +
                ' && new RegExp(' + json.dumps(pattern) + ').test(a.lookup("device") || "") && ' +
                '["org.freedesktop.udisks2.modify-device", "org.freedesktop.udisks2.modify-device-system", "org.freedesktop.udisks2.modify-device-other-seat", ' +
                '"org.freedesktop.udisks2.filesystem-mount", "org.freedesktop.udisks2.filesystem-mount-system", "org.freedesktop.udisks2.filesystem-unmount-others", ' +
                '"org.freedesktop.udisks2.filesystem-take-ownership"].indexOf(a.id) >= 0) return polkit.Result.YES; });\n')
            sh("sudo", "-n", "install", "-m", "0644", str(policy_source), test_policy)
            time.sleep(1)

        time.sleep(1.0)
        mountpoint = real.mounted_at(device) or real.mount(device, "rw")
        files = {"Cours/Rpm 101.mp4": b"v" * 300_000, "Cours/Pump 02.mp4": b"w" * 120_000, "Musique/Titre.mp3": b"a" * 50_000, "notes.txt": b"hello"}
        for rel, data in files.items():
            target = Path(mountpoint) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        os.sync()
        for _ in range(20):
            if sh("udisksctl", "unmount", "-b", device, "--no-user-interaction", check_rc=False).startswith("Unmounted"):
                break
            time.sleep(0.5)
        keep = KeepAlive(device)
        keep.start()
        info = block_info(device)
        original_uuid = info["parts"][0]["uuid"] if info["parts"] else sh("lsblk", "-no", "UUID", device)
        print(f"Support de test : {device} (image {image.name}) ; aucun autre périphérique ne sera touché.")

        env = dict(os.environ, BOBINE_DATABASE_URL=f"sqlite:///{work}/test.db", BOBINE_USE_XDG="1", XDG_DATA_HOME=str(work / "xdg"),
                   XDG_CONFIG_HOME=str(work / "cfg"), BOBINE_PORT=str(args.port),
                   BOBINE_STORAGE_FORMAT_IMAGES="1", BOBINE_STORAGE_FORMAT_ONLY=device)
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(args.port), "--log-level", "warning"],
                                  cwd=ROOT / "backend", env=env, stdout=open(work / "server.log", "w"), stderr=subprocess.STDOUT)
        up = wait_for(lambda: api(base, "GET", "/api/devices/status")[0] == 200 if real._alive(base) else False, 40)
        check("backend jetable démarré (formatage restreint à l'image de test)", bool(up), f"port {args.port}, périphérique {device}")
        if not up:
            return 1
        api(base, "POST", "/api/devices/admin/enable", {"enabled": True})
        api(base, "POST", "/api/devices/admin/pin", {"pin": "123456"})
        status, caps, _ = api(base, "GET", "/api/storage/status")
        check("capacité « format » déclarée par le pilote udisks2", status == 200 and caps["capabilities"]["format"]["supported"], str(caps["capabilities"].get("format")))

        def volumes() -> list[dict]:
            return api(base, "GET", "/api/storage/volumes")[1]["volumes"]

        found = wait_for(lambda: next((v for v in volumes() if v["label"] == label_a and v["connected"]), None), 20)
        check("support de test détecté", bool(found))
        if not found:
            return 1
        key = found["key"]

        def plan(k: str, travels: list[str] | None = None):
            return api(base, "POST", "/api/storage/format/plan", {"key": k, "travels": travels or []})

        def execute(token: str, **kw):
            body = {"key": key, "token": token, "fs": "exfat", "label": "Salle1", "confirm": label_a, "acknowledged": True, "pin": "123456"}
            body.update(kw)
            return api(base, "POST", "/api/storage/format/execute", body)

        def run_job(job_id: str, timeout: float = 120.0) -> dict:
            return wait_for(lambda: next((j for j in [api(base, "GET", f"/api/storage/format/jobs/{job_id}")[1]] if j["state"] != "running"), None), timeout) or {}

        # --- bibliothèque enregistrée : refus, avec l'action « désenregistrer » ---
        status, body, _ = api(base, "POST", f"/api/storage/volumes/{key}/mount", {"mode": "ro"})
        status, body, _ = api(base, "POST", f"/api/storage/volumes/{key}/library", {"nickname": "Test"})
        check("enregistrement comme bibliothèque", status == 200, str(body))
        status, body, _ = plan(key)
        detail = body.get("detail", {}) if isinstance(body, dict) else {}
        check("plan refusé : support enregistré comme bibliothèque (action proposée)", status == 409 and detail.get("code") == "format_library_registered" and detail.get("actions"), str(detail)[:120])
        status, body, _ = api(base, "DELETE", f"/api/storage/volumes/{key}/library?purge=true")
        check("désenregistrement (jamais les fichiers)", status == 200)

        # --- plan : aucune écriture ---
        state_before_plan = block_info(device)
        status, planned, _ = plan(key, ["windows"])
        check("plan accepté", status == 200 and planned.get("token"), str(planned)[:140] if status != 200 else "")
        if status != 200:
            return 1
        target = planned["target"]
        read = planned["content"]["volumes"][0]
        check("plan : étiquette, taille, système actuel", target["name"] == label_a and target["partitions"][0]["fstype"] == "exfat" and target["size_bytes"] == GIB)
        check("plan : fichiers, dossiers et médias comptés", read.get("files") == 4 and read.get("dirs") == 2 and read["media"] == {"video": 2, "audio": 1}, str({k: read.get(k) for k in ("files", "dirs", "media")}))
        check("plan : format recommandé par le conseiller + verdicts", planned["recommended"] == "exfat" and {o["fs"] for o in planned["options"]} == {"ext4", "exfat", "vfat", "ntfs"} and all("verdict" in o for o in planned["options"]))
        check("plan : confirmation = nom du support", planned["confirm"] == {"mode": "name", "expected": label_a})
        state_after_plan = block_info(device)
        check("plan : aucune écriture (table, UUID, système de fichiers inchangés)", [(p["uuid"], p["fstype"], p["label"]) for p in state_before_plan["parts"]] == [(p["uuid"], p["fstype"], p["label"]) for p in state_after_plan["parts"]] and state_before_plan["pttype"] == state_after_plan["pttype"])
        used = sh("findmnt", "-no", "OPTIONS", device, check_rc=False)
        check("plan : lecture seule uniquement", not used or "rw" not in used.split(","), used[:50])

        # --- dérive d'identité : un autre support apparaît entre le plan et l'exécution ---
        with open(other, "wb") as handle:
            handle.truncate(64 * 1024 * 1024)
        sh("mkfs.exfat", "-L", f"AUTRE{suffix}", str(other))
        other_device = real.loop_setup(other)
        wait_for(lambda: any(v["label"] == f"AUTRE{suffix}" for v in volumes()), 15)
        time.sleep(planned["min_wait"] + 0.5)
        status, body, _ = execute(planned["token"])
        check("dérive d'identité : un autre support est apparu → tout est annulé", status == 409 and body["detail"]["code"] == "format_identity_changed", str(body)[:120])
        after_drift = block_info(device)
        check("dérive : le support n'a pas été touché", [(p["uuid"], p["fstype"]) for p in after_drift["parts"]] == [(p["uuid"], p["fstype"]) for p in state_before_plan["parts"]])
        status, body, _ = execute(planned["token"])
        check("jeton à usage unique : réutilisation refusée", status == 409 and body["detail"]["code"] == "format_token_used", str(body)[:100])
        teardown(other_device)
        other_device = None
        wait_for(lambda: not any(v["label"] == f"AUTRE{suffix}" for v in volumes()), 15)

        # --- refus à l'exécution : texte de confirmation, case ---
        status, planned, _ = plan(key, ["windows"])
        time.sleep(planned["min_wait"] + 0.5)
        status, body, _ = execute(planned["token"], confirm="mauvais")
        check("confirmation saisie incorrecte refusée", status == 400 and body["detail"]["code"] == "format_confirmation_mismatch")
        status, body, _ = execute(planned["token"], acknowledged=False)
        check("case « je comprends » obligatoire", status == 400 and body["detail"]["code"] == "format_ack_missing")
        status, body, _ = api(base, "POST", "/api/storage/format/plan", {"key": "u-inconnu"})
        check("support inconnu refusé", status == 404 and body["detail"]["code"] == "format_not_found")

        # --- formatage exFAT réel ---
        t0 = time.time()
        status, started, _ = execute(planned["token"])
        check("exécution acceptée (jeton, confirmation, cascade rejouée sur un inventaire frais)", status == 202 and started.get("job_id"), str(started)[:120])
        job = run_job(started["job_id"])
        check("formatage exFAT terminé et vérifié", job.get("state") == "done" and job.get("outcome") == "verified", f"{job.get('state')}/{job.get('outcome')} en {time.time() - t0:.1f} s ; {job.get('error')}")
        report = job.get("report") or {}
        checks_by_id = {c["id"]: c for c in report.get("checks", [])}
        check("vérification en cascade : table, type, étiquette, UUID, capacité, alignement", all(checks_by_id.get(i, {}).get("ok") for i in ("table", "filesystem", "label", "uuid", "capacity", "alignment")), str({i: c["ok"] for i, c in checks_by_id.items()}))
        check("fichier de test écrit, relu (hachage) et supprimé", checks_by_id.get("write_test", {}).get("hash_ok") is True and checks_by_id.get("write_test", {}).get("deleted") is True)
        info = block_info(device)
        part = info["parts"][0] if info["parts"] else {}
        check("table GPT, une partition", info["pttype"] == "gpt" and len(info["parts"]) == 1)
        check("partition alignée sur 1 Mio (début 2048 secteurs)", int(part.get("start") or 0) * 512 % (1024 * 1024) == 0 and int(part.get("start") or 0) == 2048, f"début {part.get('start')}")
        check("système de fichiers exFAT, étiquette demandée, nouvel UUID", part.get("fstype") == "exfat" and part.get("label") == "Salle1" and part.get("uuid") != original_uuid, f"{part.get('fstype')} {part.get('label')} {part.get('uuid')} (avant {original_uuid})")
        check("type de partition « Microsoft basic data »", "Microsoft basic data" in (part.get("parttypename") or ""), str(part.get("parttypename")))
        check("cluster exFAT adapté à la capacité (1 Gio → 32 Kio)", report.get("params", {}).get("cluster_bytes") == 32768, str(report.get("params")))
        check("formatage rapide : l'image creuse n'a pas été écrasée", allocated_kib(image) < 64 * 1024, f"{allocated_kib(image)} Kio alloués sur 1 Gio")
        opts = real.mount_options(part.get("path") or f"{device}p1")
        check("support remonté en lecture seule à la fin", "ro" in opts.split(",") and report.get("mounted_read_only") is True, opts[:50])
        check("aucun fichier de test oublié sur le support", not [p for p in Path(real.mounted_at(part.get("path") or "") or "/nonexistent").glob(".bobine-format-check-*")])
        check("ancien contenu bien effacé", not (Path(real.mounted_at(part.get("path") or "") or "/nonexistent") / "Cours").exists())

        # --- reformatage ext4 : sans blocs réservés, propriété du compte ---
        found = wait_for(lambda: next((v for v in volumes() if v["label"] == "Salle1" and v["connected"]), None), 20)
        check("le support reformaté est relisible par l'inventaire", bool(found))
        if not found:
            return 1
        key = found["key"]
        status, planned, _ = plan(key)
        check("2e plan (autre support de fichiers)", status == 200 and planned["recommended"] == "ext4", planned.get("recommended") if status == 200 else str(planned)[:100])
        time.sleep(planned["min_wait"] + 0.5)
        status, started, _ = execute(planned["token"], fs="ext4", label="Cours", confirm="Salle1")
        job = run_job(started["job_id"]) if status == 202 else {}
        report = job.get("report") or {}
        check("reformatage ext4 terminé et vérifié", job.get("state") == "done" and job.get("outcome") == "verified", f"{job.get('state')}/{job.get('outcome')} {job.get('error')} {[c for c in report.get('checks', []) if not c['ok']]}")
        info = block_info(device)
        part = info["parts"][0] if info["parts"] else {}
        check("ext4, étiquette « Cours », table GPT", part.get("fstype") == "ext4" and part.get("label") == "Cours" and info["pttype"] == "gpt" and len(info["parts"]) == 1)
        # Le noyau garde toujours une réserve interne d'au plus 4096 blocs ; `-m 5` (défaut) en réserverait 13 107 sur 1 Gio.
        reserved = report.get("params", {}).get("reserved_blocks")
        check("ext4 sans blocs réservés au superutilisateur (-m 0)", reserved is not None and reserved <= 4096, f"{reserved} blocs (réserve interne du noyau ≤ 4096 ; -m 5 donnerait 13107)")
        check("écriture possible par le compte de Bobine (propriété prise)", {c["id"]: c for c in report.get("checks", [])}.get("write_test", {}).get("hash_ok") is True)
        check("retour en lecture seule", report.get("mounted_read_only") is True)

        # --- aucun autre périphérique n'a bougé ---
        after = lsblk_state()
        unrelated_before = {k: v for k, v in before.items() if k != device}
        unrelated_after = {k: v for k, v in after.items() if k != device}
        check("aucun vrai périphérique modifié (identité, table, partitions, montages relus)", unrelated_before == unrelated_after, f"{len(unrelated_before)} disque(s) physique(s) observé(s)")
    except Exception as exc:  # noqa: BLE001
        check("exécution sans exception", False, repr(exc))
    finally:
        if keep is not None:
            keep.stop_flag.set()
            keep.join(timeout=3)
        if server is not None:
            server.send_signal(signal.SIGTERM)
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
        for dev in list(real.loops):
            teardown(dev)
            if args.authorize_image and str(work) in sh("losetup", "-a", check_rc=False):
                sh("sudo", "-n", "losetup", "-d", dev, check_rc=False)
        if test_policy:
            sh("sudo", "-n", "rm", "-f", test_policy)
        leftovers = sh("losetup", "-a", check_rc=False)
        check("nettoyage : aucun périphérique loop de ce test ne subsiste", str(work) not in leftovers)
        print("Nettoyage : périphériques loop libérés, images et données jetables supprimées.")
    failed = [r for r in real.results if not r[1]]
    if failed and (work / "server.log").exists():
        print("\n--- journal du backend jetable (fin) ---")
        print("\n".join((work / "server.log").read_text(errors="replace").splitlines()[-25:]))
    print(f"\n{len(real.results) - len(failed)}/{len(real.results)} vérifications réussies")
    shutil.rmtree(work, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
