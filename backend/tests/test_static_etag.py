"""Lot 15, correction post-déploiement (docs/audit-android-2026-09-11.md) —
régression sur `RevalidateStaticFiles` (app/main.py) : l'ETag PAR DÉFAUT de
Starlette (`FileResponse.set_stat_headers`) est `md5(mtime + "-" + taille)`,
PAS un hachage du contenu réel — contrairement à ce qu'affirmait à tort le
commentaire de cette classe avant ce correctif. Comme l'export Next.js
normalise le mtime de chaque fichier à une date fixe identique sur CHAQUE
build (reproductibilité), l'ETag ne dépendait en pratique que de la taille
en octets : deux versions différentes d'un même fichier avec la même
taille obtenaient le même ETag, et un `GET` avec `If-None-Match` recevait
un 304 à tort, servant une page HTML périmée référençant des bundles
JS/CSS qui n'existent plus dans le build courant. Reproduit concrètement
sur la tablette pilote Android après déploiement (`GET /grid/` → 304 suivi
d'une rafale de 404 sur les chunks référencés).

Ce test simule exactement ce scénario : deux fichiers de même taille en
octets, EXACTEMENT le même mtime (comme le fait le build reproductible),
mais un contenu différent — le second doit être servi intégralement
(200), jamais confondu avec le premier via un 304 à tort.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from starlette.datastructures import Headers  # noqa: E402
from starlette.staticfiles import NotModifiedResponse  # noqa: E402

from app.main import RevalidateStaticFiles  # noqa: E402


def _scope_with_if_none_match(etag: str) -> dict:
    return {"type": "http", "headers": [(b"if-none-match", etag.encode())]}


def test_content_change_with_identical_mtime_is_not_served_as_304(tmp_path):
    static_files = RevalidateStaticFiles(directory=str(tmp_path))

    file_path = tmp_path / "index.html"
    # Même taille en octets (24 caractères chacun) pour reproduire fidèlement
    # le cas réel : seule une référence de bundle change, la longueur totale
    # du fichier peut coïncider par hasard.
    old_content = b"<script src=aaaaa.js>"
    new_content = b"<script src=bbbbb.js>"
    assert len(old_content) == len(new_content)

    file_path.write_bytes(old_content)
    fixed_mtime = 318_556_800  # 01/02/1980, cf. commentaire de RevalidateStaticFiles
    os.utime(file_path, (fixed_mtime, fixed_mtime))
    stat_result = file_path.stat()

    first_response = static_files.file_response(str(file_path), stat_result, {"type": "http", "headers": []})
    etag_v1 = first_response.headers["etag"]

    # Le fichier change (nouveau build) mais garde EXACTEMENT le même mtime
    # (build reproductible) et la même taille — condition exacte du bug.
    file_path.write_bytes(new_content)
    os.utime(file_path, (fixed_mtime, fixed_mtime))
    stat_result_v2 = file_path.stat()
    assert stat_result_v2.st_mtime == stat_result.st_mtime
    assert stat_result_v2.st_size == stat_result.st_size

    second_response = static_files.file_response(
        str(file_path), stat_result_v2, _scope_with_if_none_match(etag_v1)
    )

    assert not isinstance(second_response, NotModifiedResponse), (
        "Contenu modifié servi comme 304 Not Modified malgré un mtime/taille "
        "identiques — l'ETag ne doit jamais dépendre uniquement de mtime+taille."
    )
    assert second_response.headers["etag"] != etag_v1
    assert second_response.headers["Cache-Control"] == "no-cache"


def test_if_modified_since_alone_never_triggers_a_stale_304(tmp_path):
    """Deuxième bug trouvé en testant pour de vrai sur la tablette pilote
    (au-delà du premier correctif ETag, insuffisant seul) : un client qui
    envoie SEULEMENT `If-Modified-Since` (pas `If-None-Match`) ne doit
    jamais recevoir 304 ici — `Last-Modified` reste figé au mtime normalisé
    du build reproductible (01/02/1980), donc absolument N'IMPORTE QUELLE
    date envoyée par le client le satisferait selon la RFC 7232 standard
    (`If-Modified-Since >= Last-Modified`). Reproduit et confirmé en
    conditions réelles : `curl -H "If-Modified-Since: <date récente>"` sur
    la tablette pilote recevait 304 malgré un contenu réellement différent."""
    static_files = RevalidateStaticFiles(directory=str(tmp_path))

    file_path = tmp_path / "index.html"
    file_path.write_bytes(b"<html>v1</html>")
    fixed_mtime = 318_556_800  # 01/02/1980
    os.utime(file_path, (fixed_mtime, fixed_mtime))
    stat_result = file_path.stat()

    scope_with_only_if_modified_since = {
        "type": "http",
        "headers": [(b"if-modified-since", b"Wed, 01 Jan 2025 00:00:00 GMT")],
    }
    response = static_files.file_response(str(file_path), stat_result, scope_with_only_if_modified_since)

    assert not isinstance(response, NotModifiedResponse), (
        "If-Modified-Since seul (sans If-None-Match) a déclenché un 304 — "
        "Last-Modified reste figé par le build reproductible, ce repli ne "
        "peut jamais être fiable ici."
    )
    assert response.headers["Cache-Control"] == "no-cache"


def test_unchanged_content_is_served_as_304_on_revalidation(tmp_path):
    """Le pendant positif : un fichier VRAIMENT inchangé doit toujours
    bénéficier d'un 304 (l'objectif même de la revalidation ETag), pas être
    re-téléchargé à chaque requête."""
    static_files = RevalidateStaticFiles(directory=str(tmp_path))

    file_path = tmp_path / "style.css"
    file_path.write_bytes(b"body{color:#000}")
    stat_result = file_path.stat()

    first_response = static_files.file_response(str(file_path), stat_result, {"type": "http", "headers": []})
    etag = first_response.headers["etag"]

    second_response = static_files.file_response(
        str(file_path), stat_result, _scope_with_if_none_match(etag)
    )
    assert isinstance(second_response, NotModifiedResponse)
    assert second_response.headers["Cache-Control"] == "no-cache"
