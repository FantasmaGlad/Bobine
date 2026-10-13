"""Détection des écrans externes et fenêtre projecteur desktop (plan 4.0, P1-3a).
Aucune dépendance à un affichage réel : énumération et lancement injectés."""

import json
import threading

from app.desktop.displays import (
    DisplayOrchestrator,
    DisplayWatcher,
    Monitor,
    ProjectorWindow,
    build_projector_command,
    external_monitors,
    find_kiosk_browser,
    parse_macos_displays,
    parse_xrandr_listmonitors,
    report_display_state,
)

LAPTOP = Monitor("eDP-1", 0, 0, 1920, 1080, primary=True)
PROJECTOR = Monitor("HDMI-1", 1920, 0, 1920, 1080)

XRANDR_TWO = """Monitors: 2
 0: +*eDP-1 1920/344x1080/193+0+0  eDP-1
 1: +HDMI-1 1920/527x1080/296+1920+0  HDMI-1
"""


def test_parse_xrandr_deux_moniteurs_dont_un_principal():
    monitors = parse_xrandr_listmonitors(XRANDR_TWO)
    assert monitors == [LAPTOP, PROJECTOR]


def test_parse_xrandr_ignore_les_lignes_inattendues_et_gere_un_decalage_negatif():
    out = parse_xrandr_listmonitors("Monitors: 1\n 0: +DP-2 2560/597x1440/336+-2560+0  DP-2\nbruit\n")
    assert out == [Monitor("DP-2", -2560, 0, 2560, 1440, primary=False)]
    assert parse_xrandr_listmonitors("") == []


def test_parse_xrandr_moniteur_defini_a_la_main_sans_prefixe_plus():
    """Constaté sur une vraie session XWayland : `xrandr --setmonitor` écrit le
    moniteur SANS le « + » des sorties RandR."""
    out = parse_xrandr_listmonitors(
        "Monitors: 2\n 0: +*eDP-1 3072/340x1920/220+0+0  eDP-1\n 1: projecteur-virtuel 1920/508x1080/286+3072+0 \n"
    )
    assert out == [Monitor("eDP-1", 0, 0, 3072, 1920, True), Monitor("projecteur-virtuel", 3072, 0, 1920, 1080, False)]
    assert parse_xrandr_listmonitors(" 0: *DP-1 1920/1x1080/1+0+0  DP-1")[0].primary is True


def test_parse_macos_system_profiler():
    payload = json.dumps({"SPDisplaysDataType": [{"spdisplays_ndrvs": [
        {"_name": "Color LCD", "_spdisplays_resolution": "2560 x 1600 @ 60.00Hz", "spdisplays_main": "spdisplays_yes"},
        {"_name": "Projecteur", "_spdisplays_resolution": "1920 x 1080 @ 60.00Hz"},
    ]}]})
    monitors = parse_macos_displays(payload)
    assert [(m.name, m.width, m.primary) for m in monitors] == [("Color LCD", 2560, True), ("Projecteur", 1920, False)]
    assert parse_macos_displays("pas du json") == []


def test_external_monitors():
    assert external_monitors([]) == []
    assert external_monitors([LAPTOP]) == []
    assert external_monitors([LAPTOP, PROJECTOR]) == [PROJECTOR]
    # Aucun moniteur marqué principal : le premier fait office de principal.
    assert external_monitors([Monitor("A", 0, 0, 1, 1), Monitor("B", 1, 0, 1, 1)]) == [Monitor("B", 1, 0, 1, 1)]


def test_commande_projecteur_positionnee_avec_profil_dedie():
    cmd = build_projector_command("/usr/bin/chromium", "http://127.0.0.1:8000/cinema/?channel=cable", PROJECTOR, "/tmp/p")
    assert cmd[0] == "/usr/bin/chromium"
    assert "--user-data-dir=/tmp/p" in cmd
    assert "--window-position=1920,0" in cmd
    assert "--window-size=1920,1080" in cmd
    assert "--kiosk" in cmd and "--autoplay-policy=no-user-gesture-required" in cmd
    assert cmd[-1] == "http://127.0.0.1:8000/cinema/?channel=cable"
    assert "--ozone-platform=x11" not in cmd
    assert "--ozone-platform=x11" in build_projector_command("b", "u", PROJECTOR, "/tmp/p", wayland=True)


def test_choix_du_navigateur():
    assert find_kiosk_browser("Linux", which=lambda n: "/usr/bin/chromium" if n == "chromium" else None) == "/usr/bin/chromium"
    assert find_kiosk_browser("Linux", which=lambda n: None) is None
    assert find_kiosk_browser("Windows", which=lambda n: r"C:\edge.exe" if n == "msedge" else None) == r"C:\edge.exe"
    found = find_kiosk_browser(
        "Windows", which=lambda n: None, exists=lambda p: p.endswith("chrome.exe"),
        environ={"ProgramFiles": r"C:\Program Files"},
    )
    assert found and found.endswith("chrome.exe")
    # macOS : fenêtre native (P1-3b), jamais un navigateur piloté ici.
    assert find_kiosk_browser("Darwin", which=lambda n: "/x") is None


class FakeProcess:
    def __init__(self):
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


def _projector(launches):
    def popen(command, **kwargs):
        proc = FakeProcess()
        launches.append((command, proc))
        return proc

    return ProjectorWindow("http://x/cinema", browser_finder=lambda: "/bin/chromium", popen=popen,
                           profile_factory=lambda: "/tmp/fake-profile")


def test_fenetre_projecteur_idempotente_deplacee_puis_fermee():
    launches = []
    window = _projector(launches)
    assert window.show_on(PROJECTOR) is True
    assert window.show_on(PROJECTOR) is True
    assert len(launches) == 1  # même moniteur : pas de relance
    other = Monitor("DP-1", 3840, 0, 2560, 1440)
    window.show_on(other)
    assert len(launches) == 2 and launches[0][1].terminated is True  # ancienne fenêtre fermée
    window.close()
    assert launches[1][1].terminated is True and window.is_open is False


def test_fenetre_projecteur_sans_navigateur_ne_leve_pas():
    window = ProjectorWindow("u", browser_finder=lambda: None, popen=lambda *a, **k: None)
    assert window.show_on(PROJECTOR) is False


def test_relance_si_la_fenetre_a_ete_fermee_par_l_utilisateur_au_prochain_changement():
    launches = []
    window = _projector(launches)
    window.show_on(PROJECTOR)
    launches[0][1].terminated = True  # fenêtre fermée à la main
    assert window.is_open is False
    window.show_on(PROJECTOR)
    assert len(launches) == 2


def test_watcher_exige_une_lecture_stable_avant_de_notifier():
    seen = []
    readings = iter([[LAPTOP], [LAPTOP, PROJECTOR], [LAPTOP], [LAPTOP], [LAPTOP, PROJECTOR], [LAPTOP, PROJECTOR]])
    watcher = DisplayWatcher(seen.append, list_fn=lambda: next(readings), stable_polls=2)
    state: dict = {}
    for _ in range(6):
        watcher.poll_once(state)
    # [LAPTOP] vu 1x puis un clignotement ignoré ; confirmé à la 2e lecture
    # identique ([LAPTOP] x2), puis [LAPTOP, PROJECTOR] x2.
    assert [len(m) for m in seen] == [1, 2]


def test_watcher_survit_a_une_erreur_d_enumeration():
    seen = []
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("xrandr indisponible")
        return [LAPTOP]

    watcher = DisplayWatcher(seen.append, list_fn=flaky, stable_polls=1)
    state: dict = {}
    watcher.poll_once(state)
    watcher.poll_once(state)
    assert len(seen) == 1


def test_orchestrateur_branche_puis_debranche():
    launches = []
    reports = []
    orchestrator = DisplayOrchestrator(
        "http://x/api/display/state", _projector(launches),
        reporter=lambda url, count, resolution: reports.append((count, resolution)) or True,
    )
    orchestrator.handle_change([LAPTOP, PROJECTOR])
    orchestrator.join()
    assert (1, "1920x1080") in reports
    assert len(launches) == 1 and "--window-position=1920,0" in launches[0][0]
    orchestrator.handle_change([LAPTOP])
    orchestrator.join()
    assert (0, None) in reports
    assert launches[0][1].terminated is True


def test_orchestrateur_attend_le_backend_avant_d_ouvrir_la_fenetre():
    launches = []
    ready = {"value": False}
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        ready["value"] = len(waits) >= 3  # le backend devient prêt après 3 attentes

    orchestrator = DisplayOrchestrator(
        "u", _projector(launches), reporter=lambda *a: True,
        ready_check=lambda: ready["value"], sleep=sleep,
    )
    orchestrator.handle_change([LAPTOP, PROJECTOR])
    orchestrator.join()
    assert len(waits) >= 3 and len(launches) == 1


def test_orchestrateur_une_topologie_recente_annule_l_ouverture_obsolete():
    launches = []
    gate = threading.Event()
    orchestrator = DisplayOrchestrator(
        "u", _projector(launches), reporter=lambda *a: True,
        ready_check=lambda: gate.is_set(), sleep=lambda s: None,
    )
    orchestrator.BACKEND_WAIT_SECONDS = 0.5
    orchestrator.handle_change([LAPTOP, PROJECTOR])   # attend le backend
    orchestrator.handle_change([LAPTOP])              # débranché entre-temps
    gate.set()
    orchestrator.join()
    assert launches == []  # la fenêtre obsolète n'a jamais été ouverte


def test_reouverture_manuelle_et_absence_d_ecran():
    launches = []
    orchestrator = DisplayOrchestrator("u", _projector(launches), reporter=lambda *a: True)
    assert orchestrator.reopen_projector() is False
    orchestrator.handle_change([LAPTOP, PROJECTOR])
    orchestrator.join()
    launches[0][1].terminated = True
    assert orchestrator.reopen_projector() is True
    assert len(launches) == 2


def test_rapport_au_backend_rejoue_jusqu_au_succes_puis_cede_la_place_au_plus_recent():
    attempts = []

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(request, timeout=None):
        attempts.append(json.loads(request.data))
        if len(attempts) < 3:
            raise OSError("backend pas prêt")
        return Resp()

    assert report_display_state("http://x", 1, "1920x1080", source="linux", sleep=lambda s: None, urlopen=urlopen) is True
    assert len(attempts) == 3 and attempts[-1] == {"external_count": 1, "source": "linux", "resolution": "1920x1080"}

    # Un rapport plus récent annule les tentatives du précédent.
    calls = []

    def failing(request, timeout=None):
        calls.append(1)
        raise OSError("down")

    def sleeper(_):
        if len(calls) == 2:
            report_display_state("http://x", 0, source="linux", sleep=lambda s: None, urlopen=lambda r, timeout=None: Resp())

    assert report_display_state("http://x", 1, source="linux", sleep=sleeper, urlopen=failing, max_attempts=10) is False
    assert len(calls) <= 3
