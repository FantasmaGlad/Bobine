import os
import platform
import sys
import tomllib
from pathlib import Path
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseSettings

    SettingsConfigDict = None

from app.utils.android_runtime import is_android

if getattr(sys, "frozen", False):
    if platform.system() == "Darwin":
        ROOT_DIR = Path(sys.executable).resolve().parent.parent / "Resources"
    else:
        ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent


def _data_root() -> Path:
    if is_android():
        android_data_dir = os.environ.get("BOBINE_ANDROID_DATA_DIR")
        if android_data_dir:
            target = Path(android_data_dir)
            try:
                target.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return target
        return ROOT_DIR
    if platform.system() == "Windows":
        program_data = os.environ.get("ProgramData")
        if program_data:
            return Path(program_data) / "Bobine"
    elif platform.system() == "Darwin":
        target = Path.home() / "Library" / "Application Support" / "Bobine"
        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return target
    elif platform.system() == "Linux":
        if getattr(sys, "frozen", False) or not os.access(ROOT_DIR, os.W_OK) or os.environ.get("BOBINE_USE_XDG") == "1":
            xdg_data = os.environ.get("XDG_DATA_HOME")
            base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
            target = base / "bobine"
            try:
                target.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return target
    return ROOT_DIR


DATA_ROOT = _data_root()


def _android_internal_root() -> Path | None:
    if not is_android():
        return None
    android_internal_dir = os.environ.get("BOBINE_ANDROID_INTERNAL_DIR")
    if not android_internal_dir:
        return None
    target = Path(android_internal_dir)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    return target


_ANDROID_INTERNAL_ROOT_FIELDS = {"thumbnails_dir", "branding_dir", "logs_dir", "radio_covers_dir"}


def _global_config_path() -> Path:
    if platform.system() == "Windows":
        program_data = os.environ.get("ProgramData")
        if program_data:
            return Path(program_data) / "Bobine" / "config.toml"
    elif platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Bobine" / "config.toml"
    elif platform.system() == "Linux" and not is_android():
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        user_config = (Path(xdg_config) if xdg_config else Path.home() / ".config") / "bobine" / "config.toml"
        if user_config.exists():
            return user_config
    return Path("/etc/bobine/config.toml")


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/database.db"

    media_dir: str = "data/videos"
    watch_dir: str = "data/watched"
    thumbnails_dir: str = "data/thumbnails"

    backgrounds_dir: str = "data/backgrounds"
    backgrounds_watch_dir: str = "data/backgrounds_watched"

    audio_dir: str = "data/audio"
    audio_watch_dir: str = "data/audio_watched"

    radio_dir: str = "data/radio"
    radio_covers_dir: str = "data/radio_covers"
    radio_announcements_dir: str = "data/radio_announcements"
    radio_watch_dir: str = "data/radio_watched"

    branding_dir: str = "data/branding"

    logs_dir: str = "data/logs"

    subtitles_dir: str = "data/subtitles"

    audio_chain_timer_seconds: int = 5

    host: str = "0.0.0.0"
    port: int = 1903

    wait_time_between_courses: int = 0
    volume_default: int = 100
    logs_retention_days: int = 7

    radio_volume_default: int = 100
    radio_crossfade_seconds: int = 4
    radio_announcement_duck_level: int = 15
    radio_announcement_fade_ms: int = 1500
    radio_autostart_on_boot: bool = True

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_prefix="BOBINE_")
    else:

        class Config:
            env_prefix = "BOBINE_"

    @property
    def technical_log_path(self) -> Path:
        return Path(self.logs_dir) / "technical.log"


def load_settings() -> Settings:
    local_config = ROOT_DIR / "config.toml"
    global_config = _global_config_path()

    config_path = None
    if global_config.exists():
        config_path = global_config
    elif local_config.exists():
        config_path = local_config

    config_data = {}
    if config_path:
        try:
            with open(config_path, "rb") as f:
                config_data = tomllib.load(f)
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration TOML: {e}", file=sys.stderr)

    flat_config = {}
    for section_key, section_val in config_data.items():
        if isinstance(section_val, dict):
            for k, v in section_val.items():
                flat_config[k] = v
        else:
            flat_config[section_key] = section_val

    for field_name in list(flat_config.keys()):
        if f"BOBINE_{field_name.upper()}" in os.environ:
            del flat_config[field_name]

    settings = Settings(**flat_config)

    for path_attr in [
        "media_dir",
        "watch_dir",
        "thumbnails_dir",
        "backgrounds_dir",
        "backgrounds_watch_dir",
        "audio_dir",
        "audio_watch_dir",
        "radio_dir",
        "radio_covers_dir",
        "radio_announcements_dir",
        "radio_watch_dir",
        "branding_dir",
        "logs_dir",
        "subtitles_dir",
    ]:
        path_str = getattr(settings, path_attr)
        path = Path(path_str)
        if not path.is_absolute():
            root = DATA_ROOT
            if path_attr in _ANDROID_INTERNAL_ROOT_FIELDS:
                internal_root = _android_internal_root()
                if internal_root is not None:
                    root = internal_root
            setattr(settings, path_attr, str((root / path).resolve()))

    if settings.database_url.startswith("sqlite:///"):
        db_path_str = settings.database_url[len("sqlite:///"):]
        db_path = Path(db_path_str)
        if not db_path.is_absolute():
            db_root = _android_internal_root() or DATA_ROOT
            settings.database_url = f"sqlite:///{(db_root / db_path).resolve()}"

    _apply_db_overrides(settings)
    return settings


_DB_OVERRIDABLE_FIELDS = (
    "wait_time_between_courses",
    "volume_default",
    "audio_chain_timer_seconds",
    "radio_volume_default",
    "radio_crossfade_seconds",
    "radio_announcement_duck_level",
    "radio_announcement_fade_ms",
)


def _apply_db_overrides(settings: "Settings") -> None:
    if not settings.database_url.startswith("sqlite:///"):
        return
    db_path = Path(settings.database_url[len("sqlite:///"):])
    if not db_path.exists():
        return

    import sqlite3

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return

    overrides = {key: value for key, value in rows if key in _DB_OVERRIDABLE_FIELDS}
    for key, value in overrides.items():
        try:
            setattr(settings, key, int(value))
        except (TypeError, ValueError):
            pass


settings = load_settings()


def reload_settings() -> None:
    new_settings = load_settings()
    for field in getattr(settings, "model_fields", None) or settings.__fields__:
        if hasattr(new_settings, field):
            setattr(settings, field, getattr(new_settings, field))
