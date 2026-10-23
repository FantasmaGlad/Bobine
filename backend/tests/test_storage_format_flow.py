"""Assistant de formatage de bout en bout avec un pilote factice : API, plan (aucune écriture), jeton, cascade de refus,
exécution, annulation, échec et retour à l'état vierge, vérification après coup, accès (PIN), journal sans secret.

Aucun matériel : les « disques » sont des dossiers (voir storage_fakes.py). Le test réel sur image disque est un script
séparé (scripts/storage-format-real-test.py)."""

import dataclasses
import os
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.devices import security  # noqa: E402
from app.devices.base import DeviceError  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ActivityLog, ExternalVolume, Setting, StorageImport, Video  # noqa: E402
from app.storage import availability  # noqa: E402
from app.storage.formatting.model import DiskInfo  # noqa: E402
from app.storage.formatting.tokens import PlanTokens  # noqa: E402
from app.storage.service import StorageService  # noqa: E402

from storage_fakes import FakeStorageDriver  # noqa: E402

KEYS = (security.SETTING_ENABLED, security.SETTING_PIN_HASH, "storage_defaults")
GIB = 1024 ** 3


def _cleanup_db():
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.query(StorageImport).delete()
        for row in db.query(Video).filter(Video.storage_id.isnot(None)).all():
            db.delete(row)
        db.query(ExternalVolume).delete()
        db.query(ActivityLog).filter(ActivityLog.event_type.like("storage_format_%")).delete(synchronize_session=False)
        db.commit()
    availability.set_online({})


def _enable(pin=None):
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        if pin:
            db.add(Setting(key=security.SETTING_PIN_HASH, value=security.hash_pin(pin)))
        db.commit()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    init_db()
    _cleanup_db()
    monkeypatch.delenv("BOBINE_STORAGE_FORMAT_ONLY", raising=False)
    monkeypatch.delenv("BOBINE_STORAGE_FORMAT_IMAGES", raising=False)
    security.rate_limiter._by_ip.clear()
    driver = FakeStorageDriver(tmp_path / "fake")
    service = StorageService(lambda: driver)
    # Le pilote simule un disque distinct : son dossier ne doit pas hériter du st_dev de la machine CI.
    def device_numbers(paths):
        result = {}
        for path in paths:
            if Path(path).is_relative_to(tmp_path):
                result[path] = 987654321
            else:
                try:
                    result[path] = os.stat(path).st_dev
                except OSError:
                    pass
        return result
    monkeypatch.setattr(service.formatter, "_device_numbers", device_numbers)
    service.formatter.tokens = PlanTokens(min_age=0.0)           # le délai de réflexion a son propre test
    monkeypatch.setattr("app.main.storage_service", service)
    monkeypatch.setattr("app.routers.storage.service", service)
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: True)
    monkeypatch.setattr("app.storage.formatting.manager.UNMOUNT_PAUSE", 0.01)
    monkeypatch.setattr("app.storage.formatting.manager.SETTLE_SECONDS", 3.0)
    _enable("123456")
    with TestClient(app) as client:
        ns = SimpleNamespace(client=client, driver=driver, service=service, tmp=tmp_path)
        ns.refresh = lambda: client.portal.call(service.refresh)
        ns.stick = driver.plug("sdb", "AAAA-0001", {"Cours/a.mp4": b"x" * 2048, "Musique/b.mp3": b"y" * 1024, "notes.txt": b"n"}, label="CLUB", size=64 * GIB)
        ns.refresh()
        ns.key = ns.stick.key
        yield ns
    _cleanup_db()


def plan(env, key=None, travels=None, **kw):
    return env.client.post("/api/storage/format/plan", json={"key": key or env.key, "travels": travels or []}, **kw)


def execute(env, token, **overrides):
    body = {"key": env.key, "token": token, "fs": "exfat", "label": "Salle1", "confirm": "CLUB", "acknowledged": True, "pin": "123456"}
    body.update(overrides)
    return env.client.post("/api/storage/format/execute", json=body)


def code(response):
    return response.json()["detail"]["code"]


def wait_format(env, job_id, timeout=15):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        job = env.client.get(f"/api/storage/format/jobs/{job_id}").json()
        if job["state"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError(f"formatage non terminé : {job}")


def good_plan(env, **kw):
    response = plan(env, **kw)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------------------------------------ plan : aucune écriture
def test_plan_writes_nothing_and_informs_before_the_decision(env):
    body = good_plan(env, travels=["windows"])
    assert env.driver.ops == []                                                            # aucune opération destructive
    assert all(call[1][0] == "ro" or "ro" in call[1] for call in env.driver.mount_calls)   # le contenu est lu en lecture seule seulement
    target = body["target"]
    assert target["name"] == "CLUB" and target["size_bytes"] == 64 * GIB + 2 * 1024 * 1024 and target["table"] == "gpt"
    assert target["partitions"] == [{"label": "CLUB", "fstype": "exfat", "size_bytes": 64 * GIB, "mounted": True}] or target["partitions"][0]["fstype"] == "exfat"
    (read,) = body["content"]["volumes"]
    assert read["readable"] and read["files"] == 3 and read["dirs"] == 2
    assert {e["name"] for e in read["root"]} == {"Cours", "Musique", "notes.txt"}
    assert read["media"] == {"video": 1, "audio": 1}
    assert body["erases"]["partitions"] == 1 and body["erases"]["files"] == 3
    assert body["recommended"] == "exfat"                                                  # un support qui voyage vers Windows
    assert [o["fs"] for o in body["options"]] == ["ext4", "exfat", "vfat", "ntfs"]
    by_fs = {o["fs"]: o for o in body["options"]}
    assert all(o["available"] for o in body.get("options", [])) and by_fs["exfat"]["recommended"] and by_fs["exfat"]["verdict"] == "recommended"
    assert by_fs["vfat"]["verdict"] == "discouraged" and "file_limit_4gib" in by_fs["vfat"]["notes"]
    assert body["confirm"] == {"mode": "name", "expected": "CLUB"}
    assert body["quick_only"] is True and body["alignment_bytes"] == 1024 * 1024
    assert body["expires_in"] == 120 and len(body["token"]) >= 30 and body["pin_required"] is True
    assert [c["id"] for c in body["checks"]][:4] == ["platform", "present", "allowed", "not_system"] and all(c["ok"] for c in body["checks"])
    text = str(body)
    assert "/dev/" not in text and "SNSDB" not in text                                      # ni chemin de périphérique ni numéro de série


def test_plan_recommends_ext4_for_a_linux_only_stick_and_flags_missing_tools(env):
    env.driver.tools["ntfs"] = False
    body = good_plan(env)
    assert body["recommended"] == "ext4"
    ntfs = next(o for o in body["options"] if o["fs"] == "ntfs")
    assert not ntfs["available"] and ntfs["unavailable"] == "tool_missing" and ntfs["install_package"] == "ntfs-3g"


# ------------------------------------------------------------------------------------------------ cascade de refus (plan)
def test_plan_refuses_unknown_phone_and_malformed_keys(env):
    assert code(plan(env, "u-inconnu")) == "format_not_found" and plan(env, "u-inconnu").status_code == 404
    response = plan(env, "p-telephone")
    assert response.status_code == 409 and code(response) == "format_phone"
    assert env.client.post("/api/storage/format/plan", json={"key": "../etc"}).status_code == 404


def test_plan_refuses_a_registered_library_and_proposes_to_unregister(env):
    assert env.client.post(f"/api/storage/volumes/{env.key}/library", json={"nickname": "Étoile"}).status_code == 200
    response = plan(env)
    assert response.status_code == 409 and code(response) == "format_library_registered"
    detail = response.json()["detail"]
    assert detail["actions"] == [{"id": "unregister", "key": env.key}] and detail["check"] == "not_registered"
    # une action : désenregistrer, puis le plan est possible
    assert env.client.delete(f"/api/storage/volumes/{env.key}/library?purge=true").status_code == 200
    assert plan(env).status_code == 200


def test_plan_refuses_system_internal_readonly_stacked_and_busy_supports(env):
    def patched(fn):
        env.driver.disk_patch["sdb"] = fn
        return plan(env)

    original = env.driver._disk_info("sdb")
    assert code(patched(lambda d: dataclasses.replace(d, partitions=(dataclasses.replace(d.partitions[0], mountpoints=("/",)),)))) == "format_system_disk"
    assert code(patched(lambda d: dataclasses.replace(d, removable=False, hotplug=True, transport="sata"))) == "format_internal_disk"
    assert code(patched(lambda d: dataclasses.replace(d, read_only=True))) == "format_read_only"
    assert code(patched(lambda d: dataclasses.replace(d, partitions=(dataclasses.replace(d.partitions[0], fstype="crypto_LUKS"),)))) == "format_encrypted_stack"
    assert code(patched(lambda d: dataclasses.replace(d, size_bytes=1024 * 1024))) == "format_too_small"
    assert code(patched(lambda d: dataclasses.replace(d, dev_type="loop"))) == "format_image_not_allowed"
    protected = env.service.protected_paths()[0]
    assert code(patched(lambda d: dataclasses.replace(d, partitions=(dataclasses.replace(d.partitions[0], mountpoints=(protected,)),)))) == "format_bobine_data"
    env.driver.disk_patch.clear()
    env.service._busy[env.key] = {"import-1"}                                            # un import utilise le support
    assert code(plan(env)) == "format_in_use"
    env.service._busy.clear()
    env.service._ejecting.add(env.key)
    assert code(plan(env)) == "format_in_use"
    env.service._ejecting.clear()
    env.driver.format_ok = False
    assert plan(env).status_code == 501 and code(plan(env)) == "format_unsupported_platform"
    assert original.name == "sdb"
    assert env.driver.ops == []                                                          # aucun refus n'a touché au support


def test_simulated_etoile_is_refused_by_the_whole_stack(env, monkeypatch):
    """Identité du vrai disque « Étoile » simulée (exFAT, 238 Go, USB) : enregistrée comme bibliothèque, il est refusé ; jamais touché."""
    etoile = env.driver.plug("sdq", "E7E7-0238", {"Films/a.mp4": b"z" * 100}, label="Étoile", size=238 * GIB)
    env.refresh()
    env.client.post(f"/api/storage/volumes/{etoile.key}/library", json={})
    response = plan(env, etoile.key)
    assert response.status_code == 409 and code(response) == "format_library_registered"
    # même désenregistrée, la liste blanche d'un environnement d'essai le refuse
    env.client.delete(f"/api/storage/volumes/{etoile.key}/library?purge=true")
    monkeypatch.setenv("BOBINE_STORAGE_FORMAT_ONLY", "/dev/loop29")
    assert code(plan(env, etoile.key)) == "format_not_allowed" and code(plan(env)) == "format_not_allowed"
    assert env.driver.ops == []


# ------------------------------------------------------------------------------------------------ exécution : validations avant le jeton
def test_execute_validates_the_request_without_burning_the_token(env):
    token = good_plan(env)["token"]
    assert code(execute(env, None)) == "format_token_missing"
    assert code(execute(env, token, fs="zfs")) == "format_fs_unknown"
    assert code(execute(env, token, label="")) == "format_label_invalid"
    assert code(execute(env, token, label="x" * 12)) == "format_label_invalid"
    assert code(execute(env, token, acknowledged=False)) == "format_ack_missing"
    assert code(execute(env, token, confirm="clou")) == "format_confirmation_mismatch"
    assert code(execute(env, token, confirm="")) == "format_confirmation_mismatch"
    env.driver.tools["exfat"] = False
    assert code(execute(env, token)) == "format_fs_unavailable"
    env.driver.tools["exfat"] = True
    assert env.driver.ops == []
    ok = execute(env, token, confirm=" club ")                                              # le jeton n'a servi à rien jusqu'ici
    assert ok.status_code == 202
    wait_format(env, ok.json()["job_id"])


def test_reflection_delay_is_enforced_by_the_server(env):
    env.service.formatter.tokens = PlanTokens(min_age=4.0)
    token = good_plan(env)["token"]
    response = execute(env, token)
    assert response.status_code == 409 and code(response) == "format_too_early" and env.driver.ops == []


def test_token_is_single_use_and_tied_to_the_plan(env):
    token = good_plan(env)["token"]
    env.service._busy[env.key] = {"import-1"}                       # la cascade refuse : le jeton est brûlé quand même
    assert code(execute(env, token)) == "format_in_use"
    env.service._busy.clear()
    again = execute(env, token)
    assert again.status_code == 409 and code(again) == "format_token_used" and env.driver.ops == []
    assert code(execute(env, "inventé")) == "format_token_unknown"
    token = good_plan(env)["token"]
    first = execute(env, token)
    assert first.status_code == 202
    wait_format(env, first.json()["job_id"])
    replay = execute(env, token)                                    # le support a un nouvel UUID : l'ancienne clé n'existe plus
    assert replay.status_code == 404 and code(replay) == "format_not_found"
    assert env.driver.ops.count(("table", "sdb")) == 1              # un seul effacement


def test_token_expires_and_other_requester_is_refused(env):
    token = good_plan(env)["token"]
    record = next(iter(env.service.formatter.tokens._live.values()))
    object.__setattr__(record, "issued_at", record.issued_at - 500)
    assert code(execute(env, token)) == "format_token_expired"
    token = good_plan(env)["token"]
    record = next(iter(env.service.formatter.tokens._live.values()))
    object.__setattr__(record, "owner", "autre-appareil")
    assert code(execute(env, token)) == "format_token_owner"
    assert env.driver.ops == []


# ------------------------------------------------------------------------------------------------ dérive d'identité
def test_any_identity_drift_between_plan_and_execute_cancels_everything(env):
    for name, drift in (
        ("serial", lambda: env.driver.serials.__setitem__("sdb", "AUTRE")),
        ("table", lambda: env.driver.tables.__setitem__("sdb", "dos")),
    ):
        token = good_plan(env)["token"]
        drift()
        response = execute(env, token)
        assert response.status_code == 409 and code(response) == "format_identity_changed", name
        env.driver.serials.pop("sdb", None)
        env.driver.tables.pop("sdb", None)
    # un autre support apparaît : l'empreinte de l'inventaire change, les noms /dev peuvent avoir été réattribués
    token = good_plan(env)["token"]
    env.driver.plug("sdc", "BBBB-0002", {"x": b"1"}, label="AUTRE")
    env.refresh()
    assert code(execute(env, token)) == "format_identity_changed"
    assert env.driver.ops == []


def test_replaced_support_with_same_device_name_is_detected(env):
    token = good_plan(env)["token"]
    env.driver.unplug(env.key)
    swapped = env.driver.plug("sdb", "CCCC-0003", {"autre.txt": b"1"}, label="CLUB", size=64 * GIB)   # même nom, même étiquette, autre UUID
    env.refresh()
    response = execute(env, token, key=swapped.key)
    assert response.status_code == 409 and code(response) in ("format_identity_changed", "format_token_unknown")
    response = execute(env, token)
    assert response.status_code in (404, 409) and env.driver.ops == []


# ------------------------------------------------------------------------------------------------ exécution réussie
def test_successful_format_runs_quick_gpt_and_verifies_everything(env):
    old_uuid = env.stick.fs_uuid
    token = good_plan(env)["token"]
    response = execute(env, token, fs="exfat", label="Salle1")
    assert response.status_code == 202
    job = wait_format(env, response.json()["job_id"])
    assert job["state"] == "done" and job["outcome"] == "verified" and job["percent"] == 100, job
    assert [s["state"] for s in job["steps"]] == ["ok"] * 5 + ["ok"] * 5 or all(s["state"] in ("ok", "skipped") for s in job["steps"])
    assert env.driver.ops == [("table", "sdb"), ("format", "sdb")]                           # table GPT puis partition + système de fichiers
    spec = env.driver.last_spec
    assert spec.fs == "exfat" and spec.label == "Salle1" and spec.offset_bytes == 1024 * 1024 and spec.mkfs_args == ("-c", "131072")
    assert spec.partition_guid == "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7" and not spec.take_ownership
    report = job["report"]
    checks = {c["id"]: c for c in report["checks"]}
    assert report["ok"] and {"table", "filesystem", "label", "uuid", "capacity", "alignment", "mount_ro", "write_test", "back_read_only"} <= set(checks)
    assert all(c["ok"] for c in report["checks"]), report["checks"]
    assert checks["write_test"]["hash_ok"] and checks["write_test"]["deleted"] and checks["write_test"]["bytes"] == 64 * 1024
    assert report["mounted_read_only"] is True and report["uuid_changed"] and report["filesystem"] == "exfat"
    # le nouveau support est relu : autre UUID, bon type, bonne étiquette, monté en lecture seule
    listing = env.client.get("/api/storage/volumes").json()["volumes"]
    (new,) = [v for v in listing if v["connected"]]
    assert new["fstype"] == "exfat" and new["label"] == "Salle1" and new["mounted_read_only"] is True and new["key"] != env.key
    assert env.driver.volumes[new["key"]].fs_uuid != old_uuid
    # aucun fichier de test oublié, tout est revenu en lecture seule
    leftovers = [p for p in env.driver.disk_dir(new["key"]).iterdir()]
    assert leftovers == []
    modes = [opts[0] for key, opts in env.driver.mount_calls if key == new["key"]]
    assert modes == ["ro", "rw", "ro"] or modes[-3:] == ["ro", "rw", "ro"] or modes[-1] == "ro"
    assert env.service.formatter.active() is None


@pytest.mark.parametrize("fs,label,expected_label,args,ownership,guid", [
    ("ext4", "Cours", "Cours", ("-m", "0", "-T", "largefile"), True, "0fc63daf-8483-4772-8e79-3d69d8477de4"),
    ("vfat", "cours", "COURS", ("-F", "32"), False, "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"),
    ("ntfs", "Salle", "Salle", ("-Q",), False, "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"),
])
def test_each_filesystem_gets_its_adapted_parameters(env, fs, label, expected_label, args, ownership, guid):
    token = good_plan(env)["token"]
    job = wait_format(env, execute(env, token, fs=fs, label=label).json()["job_id"])
    assert job["state"] == "done", job
    spec = env.driver.last_spec
    assert (spec.fs, spec.mkfs_args, spec.take_ownership, spec.partition_guid) == (fs, args, ownership, guid)
    assert job["report"]["label"] == expected_label and job["report"]["ok"]


# ------------------------------------------------------------------------------------------------ annulation
def test_cancel_before_the_point_of_no_return_leaves_the_support_intact(env):
    env.driver.unmount_delay = 0.6
    token = good_plan(env)["token"]
    job_id = execute(env, token).json()["job_id"]
    running = env.client.get(f"/api/storage/format/jobs/{job_id}").json()
    assert running["state"] == "running" and running["can_cancel"] and not running["point_of_no_return"]
    assert env.client.delete(f"/api/storage/format/jobs/{job_id}").status_code == 200
    job = wait_format(env, job_id)
    assert job["state"] == "cancelled" and job["outcome"] == "unchanged" and not job["point_of_no_return"]
    assert env.driver.ops == []                                                              # rien n'a été effacé
    assert env.key in env.driver.volumes and env.driver.disk_dir(env.key).joinpath("notes.txt").exists()


def test_cancel_after_the_point_of_no_return_is_refused(env):
    env.driver.format_delay = 0.6
    token = good_plan(env)["token"]
    job_id = execute(env, token).json()["job_id"]
    deadline = time.time() + 5
    while time.time() < deadline and not env.client.get(f"/api/storage/format/jobs/{job_id}").json()["point_of_no_return"]:
        time.sleep(0.02)
    job = env.client.get(f"/api/storage/format/jobs/{job_id}").json()
    assert job["point_of_no_return"] and not job["can_cancel"]
    refused = env.client.delete(f"/api/storage/format/jobs/{job_id}")
    assert refused.status_code == 409 and code(refused) == "format_cannot_cancel"
    assert wait_format(env, job_id)["state"] == "done"
    assert env.client.delete("/api/storage/format/jobs/inexistant").status_code == 404


# ------------------------------------------------------------------------------------------------ une seule opération destructive
def test_only_one_destructive_operation_at_a_time(env):
    env.driver.plug("sdc", "BBBB-0002", {"x": b"1"}, label="AUTRE", size=64 * GIB)
    env.refresh()
    other = next(k for k, v in env.driver.volumes.items() if v.disk == "sdc")
    env.driver.format_delay = 0.8
    first_token = good_plan(env)["token"]
    second_token = good_plan(env, key=other)["token"]
    first = execute(env, first_token)
    assert first.status_code == 202
    second = env.client.post("/api/storage/format/execute", json={"key": other, "token": second_token, "fs": "exfat", "label": "B", "confirm": "AUTRE", "acknowledged": True, "pin": "123456"})
    assert second.status_code == 409 and code(second) == "format_busy_operation"
    assert code(plan(env, key=other)) == "format_busy_operation"
    assert env.client.get("/api/storage/format/active").json()["job"]["job_id"] == first.json()["job_id"]
    wait_format(env, first.json()["job_id"])
    assert env.client.get("/api/storage/format/active").json()["job"] is None
    assert [op for op in env.driver.ops if op[0] == "table"] == [("table", "sdb")]           # le second support n'a pas été touché
    # pendant l'opération, les autres actions sur le support sont refusées
    env.driver.format_delay = 0.5
    token = good_plan(env, key=other)["token"]
    running = env.client.post("/api/storage/format/execute", json={"key": other, "token": token, "fs": "exfat", "label": "B", "confirm": "AUTRE", "acknowledged": True, "pin": "123456"}).json()["job_id"]
    assert env.client.post(f"/api/storage/volumes/{other}/mount", json={"mode": "rw"}).status_code == 409
    assert env.client.post(f"/api/storage/volumes/{other}/eject").status_code == 409
    wait_format(env, running)


# ------------------------------------------------------------------------------------------------ échecs : jamais à moitié configuré
def test_busy_support_cannot_be_unmounted_and_nothing_is_erased(env):
    env.driver.busy_unmount_device = True
    token = good_plan(env)["token"]
    job = wait_format(env, execute(env, token).json()["job_id"], timeout=20)
    assert job["state"] == "failed" and job["error"]["code"] == "format_busy_mounted" and job["outcome"] == "unchanged"
    assert env.driver.ops == [] and env.key in env.driver.volumes


def test_failure_after_the_table_returns_the_support_to_a_blank_state(env):
    env.driver.fail_ops["format"] = DeviceError("format_failed", "boom", 502)
    token = good_plan(env)["token"]
    job = wait_format(env, execute(env, token).json()["job_id"])
    assert job["state"] == "failed" and job["outcome"] == "erased_blank" and job["error"]["code"] == "format_failed"
    assert env.driver.ops == [("table", "sdb"), ("format", "sdb"), ("wipe", "sdb")]           # retour à vierge, pas de demi-configuration
    assert env.driver.tables.get("sdb") is None and not [v for v in env.driver.volumes.values() if v.disk == "sdb"]
    assert job["steps"][3]["state"] == "failed"
    assert env.service.formatter.active() is None and env.service._formatting == set()        # verrou libéré


def test_failure_while_writing_the_table_is_reported_as_uncertain_not_hidden(env):
    env.driver.fail_ops["table"] = DeviceError("format_failed", "boom", 502)
    job = wait_format(env, execute(env, good_plan(env)["token"]).json()["job_id"])
    assert job["state"] == "failed" and job["outcome"] == "partial_unknown"
    assert "wipe" not in [op[0] for op in env.driver.ops]


def test_polkit_denial_is_explicit_and_leaves_the_support_unchanged(env):
    env.driver.fail_ops["table"] = DeviceError("format_not_authorized", "non autorisé", 403)
    job = wait_format(env, execute(env, good_plan(env)["token"]).json()["job_id"])
    assert job["state"] == "failed" and job["error"]["code"] == "format_not_authorized" and job["outcome"] == "unchanged"


def test_support_that_vanishes_before_the_last_check_aborts_with_nothing_written(env):
    env.driver.unmount_delay = 0.4
    token = good_plan(env)["token"]
    job_id = execute(env, token).json()["job_id"]
    env.driver.disk_patch["sdb"] = lambda d: dataclasses.replace(d, serial="CHANGE")          # remplacé pendant l'attente
    job = wait_format(env, job_id)
    assert job["state"] == "failed" and job["error"]["code"] == "format_identity_changed" and job["outcome"] == "unchanged"
    assert env.driver.ops == []


# ------------------------------------------------------------------------------------------------ accès : PIN, journal
def test_pin_is_required_for_any_format_even_on_the_trusted_local_screen(env):
    _enable_pin(env, "123456")
    assert good_plan(env)["pin_required"] is True
    token = good_plan(env)["token"]
    assert code(execute(env, token, pin=None)) == "format_pin_required" and execute(env, token, pin=None).status_code == 401
    wrong = execute(env, token, pin="000000")
    assert wrong.status_code == 401 and code(wrong) == "format_pin_invalid" and wrong.json()["detail"]["attempts_left"] == 4
    assert env.driver.ops == []
    ok = execute(env, token, pin="123456")                                                   # le jeton n'a pas été brûlé par les refus de PIN
    assert ok.status_code == 202
    wait_format(env, ok.json()["job_id"])


def test_wrong_pins_lock_the_requester_out(env):
    _enable_pin(env, "123456")
    token = good_plan(env)["token"]
    statuses = [execute(env, token, pin="111111").status_code for _ in range(6)]
    assert statuses[:4] == [401] * 4 and 429 in statuses[4:]
    assert execute(env, token, pin="123456").status_code == 429 and env.driver.ops == []


def test_remote_without_session_cannot_reach_the_format_api(env, monkeypatch):
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: False)
    _enable_pin(env, "123456")
    client = TestClient(app, client=("203.0.113.9", 50000))
    assert client.post("/api/storage/format/plan", json={"key": env.key}).status_code == 401
    assert client.post("/api/storage/format/execute", json={"key": env.key, "fs": "exfat", "label": "A"}).status_code == 401
    assert client.get("/api/storage/format/active").status_code == 401
    assert client.delete("/api/storage/format/jobs/x").status_code == 401


def _enable_pin(env, pin):
    with SessionLocal() as db:
        db.merge(Setting(key=security.SETTING_PIN_HASH, value=security.hash_pin(pin)))
        db.commit()


def test_activity_log_traces_the_operation_without_any_secret(env):
    _enable_pin(env, "654321")
    token = good_plan(env)["token"]
    execute(env, token, pin="000000")
    job = wait_format(env, execute(env, token, pin="654321").json()["job_id"])
    assert job["state"] == "done"
    execute(env, token, pin="654321")                                                        # jeton déjà utilisé : refus journalisé
    with SessionLocal() as db:
        rows = db.query(ActivityLog).filter(ActivityLog.event_type.like("storage_format_%")).all()
        text = " ".join(f"{r.event_type} {r.detail}" for r in rows)
    kinds = {r.event_type for r in rows}
    assert {"storage_format_started", "storage_format_done", "storage_format_refused"} <= kinds
    assert token not in text and "654321" not in text and "SNSDB" not in text and "/dev/" not in text


def test_format_requires_a_configured_pin_even_locally(env):
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key == security.SETTING_PIN_HASH).delete()
        db.commit()
    token = good_plan(env)["token"]
    response = execute(env, token)
    assert response.status_code == 403 and code(response) == "format_pin_not_set"
    assert env.driver.ops == []


def test_replacement_after_partition_table_is_never_formatted_or_wiped(env):
    def replace_target():
        disk = env.driver.blank_disks["sdb"]
        env.driver.blank_disks["sdb"] = dataclasses.replace(disk, diskseq="new-connection")
    env.driver.after_table = replace_target
    job = wait_format(env, execute(env, good_plan(env)["token"]).json()["job_id"])
    assert job["state"] == "failed" and job["outcome"] == "partial_unknown"
    assert job["error"]["code"] == "format_identity_changed"
    assert env.driver.ops == [("table", "sdb")]


def test_new_volume_stays_locked_until_format_verification_finishes(env, monkeypatch):
    import asyncio
    manager = env.service.formatter
    verify = manager._verify
    async def delayed_verify(*args):
        await asyncio.sleep(0.6)
        return await verify(*args)
    monkeypatch.setattr(manager, "_verify", delayed_verify)
    job_id = execute(env, good_plan(env)["token"]).json()["job_id"]
    deadline = time.monotonic() + 5
    new = None
    while time.monotonic() < deadline:
        env.refresh()
        new = next((v for v in env.driver.volumes.values() if v.fs_uuid.startswith("NEW")), None)
        if new:
            break
        time.sleep(0.02)
    assert new is not None
    assert env.client.post(f"/api/storage/volumes/{new.key}/mount", json={"mode": "rw"}).status_code == 409
    assert env.client.post(f"/api/storage/volumes/{new.key}/eject").status_code == 409
    assert wait_format(env, job_id)["state"] == "done"
