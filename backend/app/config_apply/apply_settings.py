"""Réglages, machine et sorties d'affichage."""
from __future__ import annotations
import json
from app.api.contract import CHANNELS
from typing import Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.utils import ui_language
from app import config_files
from app.models import (
    Setting,
)
from app.config_apply.context import _Context
from app.config_apply.resolve import _background


_START_ONLY_RADIO = {"volume_default": "radio_volume_default", "crossfade_seconds": "radio_crossfade_seconds",
                     "announcement_duck_level": "radio_announcement_duck_level"}


def _apply_settings(ctx: _Context, file: str, document: dict) -> None:
    from app.api.routes.settings.core import SettingsUpdate
    from app.api.routes.settings.values import after_settings_change, settings_updates, stage_settings

    body = document.get("settings")
    if not isinstance(body, dict):
        ctx.fail(file, "« settings » doit être un objet")
        return
    unknown = sorted(set(body) - set(config_files.PORTABLE_SETTINGS) - {"default_coach_background", "radio"})
    for key in unknown:
        ctx.fail(file, f"réglage inconnu : {key}")
    values: dict[str, Any] = {}
    for key in config_files.PORTABLE_SETTINGS:
        if key in body:
            value = body[key]
            values[key] = ("true" if value else "false") if isinstance(value, bool) else value
    if "default_coach_background" in body:
        background = _background(ctx, file, body["default_coach_background"])
        values["default_coach_background_id"] = background.id if background else 0
    _stage(ctx, file, values, SettingsUpdate, settings_updates, stage_settings, after_settings_change)
    if values.get("language") in ("fr", "en") and values["language"] != ui_language.served():
        ctx.restart_required.append("language")
    radio_value = body.get("radio")
    if radio_value is None:
        radio = {}
    elif not isinstance(radio_value, dict):
        ctx.fail(file, "« radio » doit être un objet")
        radio = {}
    else:
        radio = radio_value
    for key in sorted(set(radio) - set(_START_ONLY_RADIO)):
        ctx.fail(file, f"réglage radio inconnu : {key}")
    for key, setting_key in _START_ONLY_RADIO.items():
        if key in radio:
            value = radio[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                ctx.fail(file, f"radio.{key} doit être un entier positif")
                continue
            from app.config import settings as runtime_settings

            if value != config_files._stored_int(ctx.db, setting_key, getattr(runtime_settings, setting_key)):
                _write_setting(ctx.db, setting_key, str(value))
                ctx.restart_required.append(f"radio.{key}")


def _stage(ctx, file, values, model, to_updates, stage, after) -> None:
    if not values:
        return
    try:
        updates = to_updates(model(**values))
        stage(updates, ctx.db)
    except HTTPException as exc:
        ctx.fail(file, str(exc.detail))
        return
    except ValueError as exc:
        ctx.fail(file, str(exc))
        return

    async def effect(db: Session) -> None:
        await after(updates, db)

    ctx.effects.append(effect)


def _write_setting(db: Session, key: str, value: str | None) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def _apply_machine(ctx: _Context, file: str, document: dict) -> None:
    from app.devices.routing import ROUTES_SETTING, sanitize_routes
    from app.api.routes.settings.core import SettingsUpdate
    from app.api.routes.settings.values import after_settings_change, settings_updates, stage_settings
    from app.storage import longevity

    body = document.get("machine")
    if not isinstance(body, dict):
        ctx.fail(file, "« machine » doit être un objet")
        return
    unknown = sorted(set(body) - {
        "display_mode", "media_native", "update_tor", "update_tor_proxy", "audio_routes", "audio_outputs", "storage",
    })
    for key in unknown:
        ctx.fail(file, f"réglage machine inconnu : {key}")
    values: dict[str, Any] = {}
    for source, target in (("display_mode", "display_mode_setting"), ("media_native", "media_native"),
                           ("update_tor", "update_tor"), ("update_tor_proxy", "update_tor_proxy")):
        if source in body:
            value = body[source]
            values[target] = ("true" if value else "false") if isinstance(value, bool) else value
    _stage(ctx, file, values, SettingsUpdate, settings_updates, stage_settings, after_settings_change)
    if "audio_routes" in body:
        routes = sanitize_routes(body["audio_routes"])
        _write_setting(ctx.db, ROUTES_SETTING, json.dumps(routes, ensure_ascii=False) if routes else None)

        async def reconcile(db: Session) -> None:
            from app.devices.service import service as devices_service

            await devices_service.reconcile_routes()

        ctx.effects.append(reconcile)
    if "audio_outputs" in body:
        meta = body["audio_outputs"]
        if not isinstance(meta, dict) or len(meta) > 200 or any(
            len(str(key)) > 256 or not isinstance(value, dict) or len(str(value.get("alias") or "")) > 60
            for key, value in meta.items()
        ):
            ctx.fail(file, "« audio_outputs » invalide (200 sorties au plus, alias de 60 caractères au plus)")
        else:
            _write_setting(ctx.db, "devices_audio_meta", json.dumps(meta, ensure_ascii=False))
    if "storage" in body:
        try:
            _write_setting(ctx.db, "storage_defaults", json.dumps(longevity.normalize_settings(body["storage"])))
        except (TypeError, ValueError) as exc:
            ctx.fail(file, f"« storage » invalide : {exc}")


def _apply_display_outputs(ctx: _Context, file: str, document: dict) -> None:
    from app.api.routes.settings.core import _DISPLAY_OUTPUTS_BY_CHANNEL
    from app.api.routes.settings.display import apply_display_output, get_display_output_value

    outputs = document.get("outputs")
    if not isinstance(outputs, dict):
        ctx.fail(file, "« outputs » doit être un objet")
        return
    for channel, output in outputs.items():
        if output not in _DISPLAY_OUTPUTS_BY_CHANNEL.get(channel, ()):
            ctx.fail(file, f"sortie invalide pour {channel} : {output!r}")
        elif output != get_display_output_value(ctx.db, channel):

            async def switch(db: Session, channel=channel, output=output) -> None:
                await apply_display_output(db, channel, output)

            ctx.effects.append(switch)
    sounds = document.get("sound", {})
    if not isinstance(sounds, dict):
        ctx.fail(file, "« sound » doit être un objet")
        return
    from app.playback.manager import get_playback_manager
    from app.utils.radio_sound import sanitize_sound
    from app.utils.video_sound import video_sound_setting_key

    for channel, raw in sounds.items():
        if channel not in CHANNELS:
            ctx.fail(file, f"canal inconnu pour le son : {channel!r}")
            continue
        if not isinstance(raw, dict):
            ctx.fail(file, f"réglages de son invalides pour le canal {channel!r} (objet attendu)")
            continue
        sound = sanitize_sound(raw)
        _write_setting(ctx.db, video_sound_setting_key(channel), json.dumps(sound))

        async def set_video_sound(db: Session, channel=channel, sound=sound) -> None:
            await get_playback_manager(channel).set_sound(sound)

        ctx.effects.append(set_video_sound)
