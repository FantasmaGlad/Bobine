"""Commande `bobine output` : état, mode affiché et commandes de lecture et de radio d'une sortie."""
from __future__ import annotations

import argparse

from app.api.contract import CHANNELS, DISPLAY_OUTPUTS

from .client import Client
from .core import EXIT_OK, Output, parse_params, segment


def _title(state: dict) -> str:
    current = state.get("current_video") or state.get("current_audio_course") or state.get("current_background") or state.get("current_track")
    return (current or {}).get("title") or "-"


def output_line(output: dict) -> str:
    playback, radio = output.get("playback") or {}, output.get("radio") or {}
    return (f"{output['id']} ({output.get('label')}) : mode {output.get('mode')}, lecture {playback.get('state')} {_title(playback)}, "
            f"radio {radio.get('state')} {_title(radio)}")


def cmd_output(client: Client, out: Output, args: argparse.Namespace) -> int:
    action = args.output_action
    if action == "list":
        payload = client.request("GET", "/api/outputs")
        out.result(payload, "\n".join(output_line(output) for output in payload or []))
        return EXIT_OK
    if action == "get":
        payload = client.request("GET", f"/api/outputs/{segment(args.output)}")
    elif action == "mode":
        payload = client.request("PUT", f"/api/outputs/{segment(args.output)}/mode", body={"mode": args.mode})
    else:
        payload = client.request("POST", f"/api/outputs/{segment(args.output)}/{action}/{segment(args.action)}",
                                 body=parse_params(args.params))
    out.result(payload, output_line(payload))
    return EXIT_OK


def add_output_command(sub, common: argparse.ArgumentParser) -> None:
    command = sub.add_parser("output", parents=[common], help="sorties de diffusion : état, mode affiché, lecture et radio")
    actions = command.add_subparsers(dest="output_action", required=True)
    actions.add_parser("list", parents=[common], help="chaque sortie : mode, lecture et radio")
    actions.add_parser("get", parents=[common], help="état complet d'une sortie").add_argument("output", choices=CHANNELS)
    mode = actions.add_parser("mode", parents=[common], help="basculer le mode affiché d'une sortie")
    mode.add_argument("output", choices=CHANNELS)
    mode.add_argument("mode", choices=DISPLAY_OUTPUTS)
    for name, help_text in (("playback", "commande de lecture d'une sortie"), ("radio", "commande de la radio d'une sortie")):
        control = actions.add_parser(name, parents=[common], help=help_text,
                                     description="Mêmes actions que le WebSocket de l'interface ; paramètres en clé=valeur.")
        control.add_argument("output", choices=CHANNELS)
        control.add_argument("action", help="ex. play, pause, stop, seek, volume, load")
        control.add_argument("params", nargs="*", metavar="clé=valeur")
    command.set_defaults(run=cmd_output)
