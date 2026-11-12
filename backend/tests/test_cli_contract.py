"""Contrat entre l'API, l'interface et la commande `bobine` : une valeur se déclare une fois (app/api/contract.py), une route
n'existe pas sans commande ni exemption motivée (app/cli/routes.py), une commande ne dérive pas de l'API."""
import argparse
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.api import contract
from app import cli
from app.cli import completion as cli_completion
from app.cli import routes as cli_routes
from app.database import init_db
from app.main import app

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def api_routes() -> set[str]:
    return {f"{method.upper()} {path}" for path, ops in app.openapi()["paths"].items() for method in ops if method.upper() in METHODS}


def test_every_route_has_a_command_or_a_reasoned_exemption():
    unclassified = sorted(route for route in api_routes() if route not in cli_routes.COVERED and not cli_routes.exemption_for(route))
    assert not unclassified, (
        "Routes sans commande bobine ni exemption : ajoutez-les à COVERED (app/cli/routes.py) avec leur commande, "
        "ou à EXEMPT avec le statut never ou todo et la raison :\n  " + "\n  ".join(unclassified)
    )


def test_exemptions_do_not_overlap():
    for route in api_routes():
        rules = cli_routes.exemption_for(route)
        assert len(rules) <= 1, f"{route} : plusieurs exemptions ({[r.pattern for r in rules]})"


def test_the_table_has_no_stale_entries():
    routes = api_routes()
    assert sorted(set(cli_routes.COVERED) - routes) == [], "route couverte qui n'existe plus"
    for rule in cli_routes.EXEMPT:
        assert any(rule.matches(route) and route not in cli_routes.COVERED for route in routes), f"exemption sans route : {rule.pattern}"
        assert rule.status in ("never", "todo") and rule.reason.strip()


def test_covered_routes_name_a_real_command():
    assert set(cli_routes.COVERED.values()) <= set(cli.COMMANDS)


def test_every_command_listed_for_the_launcher_exists_in_the_parser():
    assert set(cli_completion._command_tree(cli.build_parser())[1]) == set(cli.COMMANDS)


# --- les choix du CLI sont ceux de l'API -----------------------------------------------------------------------------------

EXPECTED_CHOICES = {
    ("library", "list", "sort_by"): contract.VIDEO_SORT_FIELDS,
    ("library", "list", "order"): contract.SORT_ORDERS,
    ("schedule", "list", "channel"): contract.SCHEDULE_CHANNELS,
    ("schedule", "next", "channel"): contract.SCHEDULE_CHANNELS,
    ("metrics", "dashboard", "period"): contract.DASHBOARD_PERIODS,
    ("metrics", "dashboard", "channel"): contract.DASHBOARD_CHANNELS,
    ("metrics", "history", "period"): contract.HISTORY_PERIODS,
    ("display", "set", "channel"): contract.CHANNELS,
    ("display", "set", "output"): contract.DISPLAY_OUTPUTS,
    ("logs", None, "source"): contract.LOG_SOURCES,
    ("logs", None, "level"): contract.LOG_LEVELS,
    ("schedule", "add", "target_type"): contract.SCHEDULE_TARGETS,
    ("schedule", "add", "channel"): contract.SCHEDULE_CHANNELS,
    ("schedule", "override", "action"): contract.OVERRIDE_ACTIONS,
    ("schedule", "override", "replace_type"): contract.SCHEDULE_TARGETS,
    ("api", None, "method"): ("GET", "POST", "PUT", "PATCH", "DELETE"),
    ("completion", None, "shell"): ("bash", "zsh", "fish"),
}


def parser_choices():
    parser = cli.build_parser()
    found = {}
    top = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    for name, command in top.choices.items():
        for action in command._actions:
            if action.choices and not isinstance(action, argparse._SubParsersAction):
                found[(name, None, action.dest)] = tuple(action.choices)
        sub = next((a for a in command._actions if isinstance(a, argparse._SubParsersAction)), None)
        for sub_name, sub_parser in (sub.choices.items() if sub else []):
            for action in sub_parser._actions:
                if action.choices:
                    found[(name, sub_name, action.dest)] = tuple(action.choices)
    return found


def test_every_choice_of_the_parser_comes_from_the_contract():
    found = parser_choices()
    assert set(found) == set(EXPECTED_CHOICES), "un argument à choix a été ajouté ou retiré : le déclarer dans api_contract et ce test"
    for key, values in found.items():
        assert values == tuple(EXPECTED_CHOICES[key]), key


@pytest.fixture(scope="module")
def client():
    init_db()
    return TestClient(app)


def test_the_api_accepts_every_value_the_cli_offers(client):
    for level in contract.LOG_LEVELS:
        assert client.get("/api/logs", params={"level": level}).status_code == 200, level
    for source in contract.LOG_SOURCES:
        assert client.get("/api/logs", params={"source": source}).status_code == 200, source
    for period in contract.DASHBOARD_PERIODS:
        for channel in contract.DASHBOARD_CHANNELS:
            assert client.get("/api/metrics/dashboard", params={"period": period, "channel": channel}).status_code == 200
    for period in contract.HISTORY_PERIODS:
        assert client.get("/api/metrics/hardware/history", params={"period": period}).status_code == 200, period
    for field in contract.VIDEO_SORT_FIELDS:
        for order in contract.SORT_ORDERS:
            assert client.get("/api/videos", params={"sort_by": field, "order": order}).status_code == 200
    for channel in contract.SCHEDULE_CHANNELS:
        assert client.get("/api/schedule", params={"channel": channel}).status_code == 200, channel
        assert client.get("/api/schedule/next", params={"channel": channel}).status_code == 200, channel


def test_the_api_refuses_what_the_contract_does_not_list(client):
    assert client.get("/api/videos", params={"sort_by": "zzz"}).status_code == 422
    assert client.get("/api/videos", params={"order": "sideways"}).status_code == 422
    assert client.get("/api/metrics/dashboard", params={"period": "1y"}).status_code == 422
    assert client.get("/api/metrics/hardware/history", params={"period": "2y"}).status_code == 422
    assert client.get("/api/logs", params={"level": "loud"}).status_code == 400


def test_display_outputs_follow_the_contract(client):
    for channel, outputs in contract.DISPLAY_OUTPUTS_BY_CHANNEL.items():
        for output in outputs:
            assert client.put("/api/settings/display-output", json={"channel": channel, "output": output}).status_code == 200, (channel, output)
    refused = client.put("/api/settings/display-output", json={"channel": "network", "output": "radio"})
    assert refused.status_code in (400, 409, 422)
    client.put("/api/settings/display-output", json={"channel": "cable", "output": "kiosk"})
    client.put("/api/settings/display-output", json={"channel": "network", "output": "kiosk"})


def test_openapi_publishes_the_contract_patterns():
    patterns = {}
    for path, ops in app.openapi()["paths"].items():
        for operation in ops.values():
            for parameter in operation.get("parameters", []):
                if "pattern" in parameter.get("schema", {}):
                    patterns[(path, parameter["name"])] = parameter["schema"]["pattern"]
    assert patterns[("/api/metrics/dashboard", "period")] == contract.regex(contract.DASHBOARD_PERIODS)
    assert patterns[("/api/metrics/dashboard", "channel")] == contract.regex(contract.DASHBOARD_CHANNELS)
    assert patterns[("/api/metrics/hardware/history", "period")] == contract.regex(contract.HISTORY_PERIODS)
    assert patterns[("/api/videos", "sort_by")] == contract.regex(contract.VIDEO_SORT_FIELDS)
    assert patterns[("/api/videos", "order")] == contract.regex(contract.SORT_ORDERS)


def test_engines_and_routers_share_the_contract_values():
    from app import radio_manager
    from app.playback import manager as playback_manager
    from app.api.routes import logs, playback, schedule

    assert playback_manager.CHANNELS == contract.CHANNELS and radio_manager.RADIO_CHANNELS == contract.RADIO_CHANNELS
    assert logs.LEVELS == contract.LOG_LEVELS and schedule._CHANNELS == contract.SCHEDULE_CHANNELS
    assert playback.facade.PLAYBACK_ACTIONS is contract.PLAYBACK_ACTIONS and playback.facade.RADIO_ACTIONS is contract.RADIO_ACTIONS
    assert playback.facade.RADIO_OUTPUTS is contract.RADIO_OUTPUTS


def test_the_facade_knows_every_action_of_the_contract(client):
    for action in contract.PLAYBACK_ACTIONS:
        answer = client.post(f"/api/playback/cable/{action}", json={})
        detail = answer.json().get("detail") if answer.headers.get("content-type", "").startswith("application/json") else None
        assert not (answer.status_code == 404 and isinstance(detail, dict) and detail.get("kind") == "action"), action
    assert client.post("/api/playback/cable/zzz_inconnue", json={}).status_code == 404
    assert client.post("/api/playback/cable/stop", json={}).status_code in (200, 409)


def test_the_todo_list_only_shrinks():
    """Garde-fou : le nombre de routes sans commande prévue ne grandit pas sans décision ; le baisser (nouvelle commande)
    est la bonne direction. Mettre à jour ce plafond avec la commande qui retire des routes de `todo`."""
    todo = [route for route in api_routes() if any(r.status == "todo" for r in cli_routes.exemption_for(route))]
    assert len(todo) <= 120, f"{len(todo)} routes todo : ajouter des commandes plutôt que des exemptions"
