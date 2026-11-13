"""Commandes de consultation : état, bibliothèque, playlists, planning, appareils, stockage, mesures, imports, affichage, journaux."""

from __future__ import annotations

import argparse

from app.api.contract import CHANNELS

from .client import Client
from .core import EXIT_ERROR, EXIT_OK, EXIT_USAGE, CliError, Output, segment
from .paging import window


def cmd_status(client: Client, out: Output, args: argparse.Namespace) -> int:
    health = client.request("GET", "/api/health", accept_status={503})
    playback = {channel: client.request("GET", "/api/playback/state", query={"channel": channel}) for channel in CHANNELS}
    payload = {"health": health, "playback": playback}
    lines = [f"Bobine sur {client.base} : {health.get('status')}"]
    for channel, data in playback.items():
        current = (data.get("current_video") or data.get("current_audio_course") or data.get("current_background") or {}).get("title") or "-"
        lines.append(f"  {channel} : {data.get('state')}, {current}")
    out.result(payload, "\n".join(lines))
    return EXIT_OK if health.get("status") == "ok" else EXIT_ERROR


def cmd_library(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.library_action == "list":
        videos = client.request("GET", "/api/videos", query={
            "search": args.search, "program": args.program, "sort_by": args.sort_by, "order": args.order, **window(args),
            **({"release": args.release} if args.release else {}),
        })
        lines = []
        for video in videos:
            duration = video.get("duration_seconds")
            suffix = f" ({duration / 60:.0f} min)" if duration else ""
            lines.append(f"{video.get('id')}  {video.get('title')}{suffix}")
        out.result(videos, "\n".join(lines))
        return EXIT_OK
    video = client.request("GET", f"/api/videos/{segment(args.video_id)}")
    out.result(video, f"{video.get('id')}  {video.get('title')}")
    return EXIT_OK


def cmd_playlists(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.playlists_action == "list":
        playlists = client.request("GET", "/api/playlists", query=window(args))
        lines = [f"{p.get('id')}  {p.get('name')} ({p.get('item_count', 0)} élément(s))" for p in playlists]
        out.result(playlists, "\n".join(lines))
        return EXIT_OK
    playlist = client.request("GET", f"/api/playlists/{segment(args.playlist_id)}")
    lines = [f"{playlist.get('id')}  {playlist.get('name')}"]
    for item in playlist.get("items", []):
        video = item.get("video") or {}
        lines.append(f"  {video.get('id')}  {video.get('title')}")
    out.result(playlist, "\n".join(lines))
    return EXIT_OK


def cmd_schedule(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.schedule_action == "list":
        schedules = client.request("GET", "/api/schedule", query={"channel": args.channel, **window(args)})
        lines = []
        for schedule in schedules:
            when = schedule.get("time_of_day") or schedule.get("run_at") or "?"
            if schedule.get("days_of_week") and schedule.get("time_of_day"):
                names = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")
                when = ",".join(names[d] for d in schedule["days_of_week"] if isinstance(d, int) and 0 <= d < 7) + " " + when
            state = "actif" if schedule.get("active") else "inactif"
            lines.append(
                f"#{schedule.get('id')}  {schedule.get('channel')}  {when}  "
                f"{schedule.get('target_title') or schedule.get('target_type')}  {state}"
            )
        out.result(schedules, "\n".join(lines))
        return EXIT_OK
    if args.schedule_action == "next":
        upcoming = client.request("GET", "/api/schedule/next", query={"channel": args.channel})
        if upcoming is None:
            out.result(None, "Aucune occurrence à venir.")
        else:
            out.result(upcoming, f"{upcoming.get('run_at')}  {upcoming.get('title')}")
        return EXIT_OK
    schedule = client.request("GET", f"/api/schedule/{segment(args.schedule_id)}")
    lines = [
        f"#{schedule.get('id')}  {schedule.get('channel')}  {schedule.get('target_title') or schedule.get('target_type')}",
        f"  type={schedule.get('schedule_type')} actif={schedule.get('active')} "
        f"jours={schedule.get('days_of_week')} heure={schedule.get('time_of_day')} début={schedule.get('run_at')}",
    ]
    out.result(schedule, "\n".join(lines))
    return EXIT_OK


def cmd_devices(client: Client, out: Output, args: argparse.Namespace) -> int:
    action = args.devices_action
    payload = client.request("GET", f"/api/devices/{segment(action)}")
    if action == "status":
        lines = [
            f"{payload.get('platform')} / {payload.get('driver')}  "
            f"local={'oui' if payload.get('local') else 'non'}"
        ]
    elif action == "audio":
        if not payload.get("supported"):
            lines = [payload.get("reason") or "Sorties audio non disponibles."]
        else:
            devices = payload.get("devices", [])
            lines = [f"{len(devices)} sortie(s) audio, défaut : {payload.get('default_id') or '-'}"]
            lines += [f"  {d.get('id')}  {d.get('name')}{' (défaut)' if d.get('is_default') else ''}" for d in devices]
    elif action == "bluetooth":
        if not payload.get("supported"):
            lines = [payload.get("reason") or "Bluetooth non disponible."]
        else:
            devices = payload.get("devices", [])
            lines = [f"powered={payload.get('powered')} discovering={payload.get('discovering')} ({len(devices)} appareil(s))"]
            lines += [f"  {d.get('address')}  {d.get('name')}{' connecté' if d.get('connected') else ''}" for d in devices]
    elif action == "wifi":
        if not payload.get("supported"):
            lines = [payload.get("reason") or "Wi-Fi non disponible."]
        else:
            current = payload.get("current") or {}
            lines = [f"enabled={payload.get('enabled')}  ssid={current.get('ssid') or '-'}  ip={current.get('ip') or '-'}"]
            lines += [f"  {n.get('ssid')}  {n.get('signal')}%" for n in payload.get("networks", [])]
    else:
        counts = payload.get("counts") or {}
        lines = [
            f"{len(payload.get('nodes', []))} nœud(s), {len(payload.get('links', []))} lien(s)  "
            f"audio={counts.get('audio', 0)} bluetooth={counts.get('bluetooth', 0)} écrans={counts.get('screens', 0)}"
        ]
    out.result(payload, "\n".join(lines))
    return EXIT_OK


def cmd_storage(client: Client, out: Output, args: argparse.Namespace) -> int:
    action = args.storage_action
    if action == "browse":
        payload = client.request("GET", f"/api/storage/volumes/{segment(args.key)}/browse", query={
            "path": args.path, "limit": args.limit, **({"offset": args.offset} if args.offset else {}),
            **{name: "true" for name in ("show_hidden", "media_only") if getattr(args, name)},
        })
        lines = [f"{payload.get('path') or '/'} ({payload.get('total', 0)} élément(s))"]
        lines += [
            f"  {entry.get('type')}  {entry.get('path') or entry.get('name')}  {entry.get('size') or '-'}"
            for entry in payload.get("entries", [])
        ]
        out.result(payload, "\n".join(lines))
        return EXIT_OK
    payload = client.request("GET", f"/api/storage/{segment(action)}")
    if action == "status":
        lines = [
            f"{payload.get('driver')}  prêt={payload.get('ready')}  "
            f"libre={payload.get('free_local_bytes')} o"
        ]
    elif action == "volumes":
        volumes = payload.get("volumes", [])
        lines = [f"{len(volumes)} support(s)"]
        lines += [f"  {v.get('key')}  {v.get('name')}  {v.get('state')}" for v in volumes]
    else:
        devices = payload.get("devices", [])
        lines = [f"{len(devices)} appareil(s) portable(s)"]
        lines += [f"  {d.get('id')}  {d.get('name')}  {d.get('state')}" for d in devices]
    out.result(payload, "\n".join(lines))
    return EXIT_OK


def cmd_metrics(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.metrics_action == "dashboard":
        payload = client.request("GET", "/api/metrics/dashboard", query={
            "period": args.period, "channel": args.channel,
        })
        kpis = payload.get("kpis") or {}
        completion = kpis.get("completion") or {}
        broadcast = kpis.get("broadcast") or {}
        sessions = kpis.get("sessions") or {}
        lines = [
            f"période={payload.get('period')} canal={payload.get('channel')}",
            f"  sessions={sessions.get('total', 0)} terminées={completion.get('completed_sessions', 0)} "
            f"({completion.get('rate', 0)} %) diffusé={broadcast.get('total_hours', 0)} h",
        ]
    elif args.metrics_action == "system":
        payload = client.request("GET", "/api/settings/system")
        lines = [
            f"CPU {payload.get('cpu_percent')} % ({payload.get('cpu_temp_c')} °C)  "
            f"RAM {payload.get('memory_percent')} %  GPU {payload.get('gpu_percent')} %  "
            f"puissance {payload.get('power_watts')} W",
        ]
    else:
        payload = client.request("GET", "/api/metrics/hardware/history", query={
            "metric": args.metric, "period": args.period,
        })
        lines = [
            f"{payload.get('label')} : {payload.get('current')} {payload.get('unit')}  "
            f"min={payload.get('min')} max={payload.get('max')} moyenne={payload.get('avg')} "
            f"({payload.get('count', 0)} point(s))",
        ]
    out.result(payload, "\n".join(lines))
    return EXIT_OK


def cmd_imports(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.imports_action == "list":
        jobs = client.request("GET", "/api/import-jobs", query=window(args))
        lines = [
            f"{job.get('id')}  {job.get('stage')}  {job.get('filename')}  {job.get('progress_percent') or 0} %"
            for job in jobs
        ]
        out.result(jobs, "\n".join(lines))
        return EXIT_OK
    if args.imports_action == "cancel":
        payload = client.request("DELETE", f"/api/import-jobs/{segment(args.job_id)}")
        out.result(payload, f"Tâche {args.job_id} annulée.")
        return EXIT_OK
    report = client.request("GET", "/api/diagnostics/import")
    problems = report.get("problems") or []
    lines = [f"constat : {problem}" for problem in problems] or ["Aucun problème détecté."]
    out.result(report, "\n".join(lines))
    return EXIT_ERROR if problems else EXIT_OK


def cmd_display(client: Client, out: Output, args: argparse.Namespace) -> int:
    if args.display_action == "get":
        payload = client.request("GET", "/api/settings/display-output")
    else:
        if args.channel == "network" and args.output == "radio":
            raise CliError("la sortie radio n'est disponible que sur le canal câblé", EXIT_USAGE)
        payload = client.request("PUT", "/api/settings/display-output", body={
            "channel": args.channel, "output": args.output,
        })
    out.result(payload, f"câblé={payload.get('cable')}  réseau={payload.get('network')}")
    return EXIT_OK


def cmd_logs(client: Client, out: Output, args: argparse.Namespace) -> int:
    payload = client.request("GET", "/api/logs", query={"source": args.source, "level": args.level, "since": args.since, "limit": args.limit})
    lines = [f"{e['timestamp']} {e['level'].upper():8} {e['category']}: {e['message']}" for e in reversed(payload["entries"])]
    if payload.get("truncated"):
        lines.insert(0, out.paint(f"(plus ancien tronqué : --limit {args.limit})", "dim"))
    out.result(payload, "\n".join(lines))
    return EXIT_OK
