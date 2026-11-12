import asyncio
import logging
import logging.handlers
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, SessionLocal
from app.playback.manager import get_all_playback_managers
from app.radio_manager import get_all_radio_managers
from app.api.routes import (
    videos, playback, schedule, playlists, backgrounds, audio, audio_playlists,
    radio, radio_playlists, radio_announcements, settings as settings_router, logs, import_jobs,
    updates, metrics, display, uploads, chapters, devices, diagnostics, storage, health, media_streams,
)
from app.api.routes.media_streams import reset_stale_web_rendition_status
from app.api.static_files import mount_static_files
from app.api.errors import install_error_handlers
from app.utils.android_runtime import is_android
from app.api.http_compression import (
    ApiCompressionMiddleware,
)
from app.utils import ui_language
from app.api.network_guard import LocalNetworkGuard
from app.api.origin_guard import SameOriginGuard, dev_origins
from app.utils.deployment import get_profile_handler
from app.utils.port import active_port
from app import config_files
from app.api.routes import config_files as config_files_router
from app.utils import media_native, port80, tor_proxy
from app.utils.media_sidecar import close_current_media_client
from app.updates.orchestrator import load_persisted_state_at_startup
from app.utils.version import get_app_version
from app.scheduling.jobs import start_scheduler, stop_scheduler
from app.scheduling.radio import autostart_default_radio_playlist
from app.scheduling.resume import cancel_pending_resume, resume_running_schedules
from app.utils.importer.reconcile import reconcile_orphaned_media
from app.utils.mdns import start_mdns_responder, stop_mdns_responder
from app.utils.radio_announcement_scheduler import (
    start_radio_announcement_scheduler,
    stop_radio_announcement_scheduler,
)
from app.utils.radio_sound import load_all_sounds_into_managers
from app.utils.video_sound import load_all_video_sounds_into_managers
from app.utils.radio_mix import load_all_mixes_into_managers
from app.devices.routing import load_routes_into_managers
from app.utils.watcher import start_watcher, stop_watcher
from app.utils.ws_manager import manager as ws_manager
from app.devices.service import service as devices_service
from app.storage.service import service as storage_service

_IS_ANDROID = is_android()


settings.technical_log_path.parent.mkdir(parents=True, exist_ok=True)

_upload_tmp_dir = Path(settings.media_dir).parent / "tmp"
_upload_tmp_dir.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(_upload_tmp_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            settings.technical_log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_manager.bind_loop(asyncio.get_running_loop())
    init_db()
    with SessionLocal() as language_db:
        ui_language.set_served(settings_router.stored_language(language_db))
    load_persisted_state_at_startup()
    from app.utils.staged_uploads import purge_stale
    purge_stale()
    reset_stale_web_rendition_status()
    reconcile_orphaned_media()
    await storage_service.start()
    start_watcher()
    start_scheduler()
    start_mdns_responder(active_port())
    if get_profile_handler().tries_port80_redirect():
        await port80.start(active_port())
    config_files.schedule_mirror()
    with SessionLocal() as sound_db:
        load_all_sounds_into_managers(sound_db)
        load_all_video_sounds_into_managers(sound_db)
        load_all_mixes_into_managers(sound_db)
        load_routes_into_managers(sound_db)
        media_native.load_from_database(sound_db)
        tor_proxy.load_from_database(sound_db)
    await autostart_default_radio_playlist()
    await resume_running_schedules()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.start_position_broadcast_loop()
    for radio_manager in get_all_radio_managers().values():
        radio_manager.start_position_broadcast_loop()
    start_radio_announcement_scheduler()
    await devices_service.start()
    yield
    cancel_pending_resume()
    stop_scheduler()
    stop_watcher()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.stop_position_broadcast_loop()
    for radio_manager in get_all_radio_managers().values():
        radio_manager.stop_position_broadcast_loop()
    await stop_radio_announcement_scheduler()
    await devices_service.stop()
    await storage_service.stop()
    stop_mdns_responder()
    await port80.stop()
    tor_proxy.shutdown()
    close_current_media_client()


app = FastAPI(title="Bobine", version=get_app_version(), lifespan=lifespan)
install_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dev_origins()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(SameOriginGuard, allowed_origins=dev_origins())
app.add_middleware(config_files.ConfigMirrorTrigger)
app.add_middleware(ApiCompressionMiddleware)
app.add_middleware(LocalNetworkGuard)

app.include_router(videos.router)
app.include_router(chapters.router)
app.include_router(playback.router)
app.include_router(playlists.router)
app.include_router(schedule.router)
app.include_router(backgrounds.router)
app.include_router(audio.router)
app.include_router(audio_playlists.router)
app.include_router(radio.router)
app.include_router(radio_playlists.router)
app.include_router(radio_announcements.router)
app.include_router(settings_router.router)
app.include_router(display.router)
app.include_router(logs.router)
app.include_router(import_jobs.router)
app.include_router(uploads.router)
app.include_router(diagnostics.router)
app.include_router(updates.router)
app.include_router(metrics.router)
app.include_router(devices.router)
app.include_router(storage.router)
app.include_router(config_files_router.router)
app.include_router(playback.command_router)
app.include_router(health.router)
app.include_router(media_streams.router)

mount_static_files(app)
