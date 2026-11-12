"""Fichiers statiques servis par l'application : miniatures, logo personnalisé et frontend exporté."""

import hashlib
import logging
import platform
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.staticfiles import NotModifiedResponse

from app.config import settings
from app.utils import ui_language
from app.utils.android_runtime import is_android
from app.api.http_compression import (
    MIN_COMPRESSIBLE_SIZE,
    add_vary_accept_encoding,
    gzip_compress,
    is_compressible_media_type,
    request_allows_gzip,
)

logger = logging.getLogger(__name__)

_IS_ANDROID = is_android()


class _EnsuredDirStaticFiles(StaticFiles):
    """StaticFiles qui (re)crée son dossier avant de le contrôler : starlette lève sinon une RuntimeError
    (HTTP 500) quand le dossier n'existe pas à la première requête (stockage amovible absent au démarrage,
    remise à zéro, dossier purgé à la main). Une simple image ne doit jamais produire une 500."""

    async def check_config(self) -> None:
        try:
            Path(self.directory).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # stockage indisponible : traité ci-dessous

        try:
            await super().check_config()
        except RuntimeError:
            self.config_checked = False  # réessaiera à la requête suivante
            raise

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except RuntimeError as exc:
            if scope.get("type") != "http" or "does not exist" not in str(exc):
                raise
            from starlette.responses import PlainTextResponse

            await PlainTextResponse("Introuvable", status_code=404)(scope, receive, send)


# Frontend Next.js statique (si compilé et présent dans out/). `__file__`
# ne pointe plus vers un fichier du dépôt une fois figé par PyInstaller
# (BobineBackend.exe) : dans ce cas,
# `frontend/out/` est placé par l'installeur juste à côté de l'exécutable
# plutôt qu'à sa position relative dans le dépôt — SAUF sur macOS.
# `sys.getandroidapilevel` : attribut ajouté par le build CPython officiel
# pour Android (présent uniquement sous Chaquopy), moyen standard et fiable
# de détecter ce profil — cf. docs/ARCHITECTURE.md §3.1. Chaquopy
# place le code applicatif sous un dossier fixe `AssetFinder/app/` (pas la
# position relative réelle du dépôt) : `__file__` ne remonte donc pas à un
# `frontend/` sibling de `backend/` comme dans le cas "dépôt" ci-dessous —
# la tâche Gradle `stagePythonSources` (android/app/build.gradle.kts)
# place plutôt le frontend compilé en `frontend_out/`, sibling du paquet
# `app/` lui-même (un `.parent` de moins que dans le dépôt).
if _IS_ANDROID:
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend_out"
elif getattr(sys, "frozen", False):
    if platform.system() == "Darwin":
        frontend_out = Path(sys.executable).resolve().parent.parent / "Resources" / "frontend" / "out"
    else:
        frontend_out = Path(sys.executable).resolve().parent / "frontend" / "out"
else:
    frontend_out = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "out"


class RevalidateStaticFiles(StaticFiles):
    """StaticFiles standard, avec revalidation systématique des fichiers du
    frontend exporté (`frontend/out`).

    Deux pièges évités :

    - Les pipelines de paquetage (APK Android, PyInstaller…) normalisent le
      mtime des fichiers à une date fixe très ancienne (01/02/1980, build
      reproductible). Sans `Cache-Control` explicite, le calcul heuristique de
      fraîcheur (RFC 7234, ~10 % de l'âge depuis `Last-Modified`) rendrait la
      page et les bundles JS/CSS « frais » pendant des années : une WebView
      conserverait l'ancien code après une mise à jour. Chaque réponse porte
      donc `Cache-Control: no-cache`.
    - L'ETag par défaut de Starlette est `md5(mtime + "-" + taille)`, pas un
      hachage du contenu : avec un mtime figé, deux versions d'un même fichier
      de même taille partageraient le même ETag, et `If-Modified-Since` /
      `Last-Modified` (toujours 1980) répondraient « non modifié » à tort.
      L'ETag est donc recalculé sur le contenu réel (fichiers statiques
      légers uniquement — les médias passent par `app/utils/media_response.py`)
      et seule la comparaison `If-None-Match` est utilisée. Un client sans
      `If-None-Match` reçoit toujours le contenu complet (200).

    Compression : les fichiers texte (HTML, JS, CSS, JSON, SVG) sont servis en
    gzip quand le client l'accepte (2,7 Mo -> 0,76 Mo pour `frontend/out`). La
    version gzip est une autre représentation : son ETag est `"<md5>-gzip"`
    (jamais le même validateur que la version brute) et `Vary: Accept-Encoding`
    est posé sur tout fichier compressible. Un client qui a déjà en cache la
    version brute (`"<md5>"`) reçoit toujours un 304 tant que le contenu n'a pas
    changé : le contenu est le même, seul l'encodage diffère. Les octets gzip
    sont gardés en mémoire (clé = chemin + hash du contenu, donc invalidés par
    tout changement de fichier) dans une limite de `_GZIP_CACHE_MAX_BYTES`.
    Pas de gzip pour les requêtes `Range`, `HEAD` ou venant du bouclage
    (cf. `request_allows_gzip`).
    """

    _GZIP_CACHE_MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._gzip_cache: dict[tuple[str, str], bytes] = {}
        self._gzip_cache_bytes = 0

    def _gzipped(self, full_path, content_hash: str, data: bytes) -> bytes:
        key = (str(full_path), content_hash)
        compressed = self._gzip_cache.get(key)
        if compressed is None:
            compressed = gzip_compress(data)
            if self._gzip_cache_bytes + len(compressed) > self._GZIP_CACHE_MAX_BYTES:
                self._gzip_cache.clear()
                self._gzip_cache_bytes = 0
            self._gzip_cache[key] = compressed
            self._gzip_cache_bytes += len(compressed)
        return compressed

    async def get_response(self, path: str, scope):
        # Un chemin /api/* qui n'a trouvé aucune route (méthode non déclarée,
        # ressource absente) ne doit JAMAIS recevoir la page HTML 404 du
        # frontend : un client d'API (ou un `HEAD` de sonde) y verrait un
        # faux succès `text/html`. 404 JSON explicite à la place.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Ressource d'API introuvable")
        return await super().get_response(path, scope)

    def file_response(self, full_path, stat_result, scope, status_code: int = 200):
        request_headers = Headers(scope=scope)
        response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        data: bytes | None = None
        content_hash = ""
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            content_hash = hashlib.md5(data, usedforsecurity=False).hexdigest()
            response.headers["etag"] = f'"{content_hash}"'
        except OSError:
            # Repli sur l'ETag mtime+size par défaut de Starlette si le
            # fichier n'est plus lisible entre le stat() et cette lecture
            # (rare course, ex. suppression concurrente) — ne doit jamais
            # faire échouer la réponse (et pas de gzip dans ce cas : `data`
            # reste None).
            pass
        identity_etag = response.headers["etag"]

        gzip_etag: str | None = None
        if is_compressible_media_type(response.headers.get("content-type")):
            add_vary_accept_encoding(response.headers)
            if data is not None and len(data) >= MIN_COMPRESSIBLE_SIZE and request_allows_gzip(scope):
                gzip_etag = f'"{content_hash}-gzip"'

        # Comparaison ETag SEULE (pas `self.is_not_modified()`, qui retombe
        # sur If-Modified-Since/Last-Modified quand If-None-Match est
        # absent — cf. point 2 ci-dessus, c'est précisément ce repli qui
        # servait du contenu périmé). Absence d'If-None-Match == pas de
        # cache connu valide == contenu complet, jamais un 304 par défaut.
        if_none_match = request_headers.get("if-none-match")
        if if_none_match:
            client_tags = {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}
            matched = next((tag for tag in (gzip_etag, identity_etag) if tag and tag in client_tags), None)
            if matched:
                response.headers["etag"] = matched
                response = NotModifiedResponse(response.headers)
                gzip_etag = None
        if gzip_etag is not None:
            headers = {
                name: value
                for name, value in response.headers.items()
                # `accept-ranges` : la version gzip est servie d'un bloc.
                if name not in ("content-length", "etag", "accept-ranges")
            }
            headers["etag"] = gzip_etag
            headers["content-encoding"] = "gzip"
            response = Response(
                self._gzipped(full_path, content_hash, data),
                status_code=status_code,
                headers=headers,
            )
        response.headers["Cache-Control"] = "no-cache"
        return response


def mount_static_files(app: FastAPI) -> None:
    """Monte les dossiers statiques, le frontend en dernier : sa route générique masquerait les autres."""
    # Miniatures
    thumbnails_path = Path(settings.thumbnails_dir)
    thumbnails_path.mkdir(parents=True, exist_ok=True)
    app.mount("/api/thumbnails", _EnsuredDirStaticFiles(directory=str(thumbnails_path)), name="thumbnails")

    # Branding (logo personnalisé) : DOIT être
    # monté avant le catch-all frontend ci-dessous, sinon la route serait masquée.
    branding_path = Path(settings.branding_dir)
    branding_path.mkdir(parents=True, exist_ok=True)
    app.mount("/api/branding", StaticFiles(directory=str(branding_path)), name="branding")

    if frontend_out.exists():
        logger.info(f"Montage du frontend statique depuis {frontend_out}")
        app.mount("/", ui_language.LanguageFrontend(frontend_out, RevalidateStaticFiles), name="frontend")
    else:
        logger.warning("Dossier frontend/out introuvable. Le frontend ne sera pas servi par FastAPI (dev direct).")
