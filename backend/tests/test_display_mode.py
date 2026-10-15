"""Mode d'affichage câblé dérivé du matériel."""

import os

# Base de test isolée AVANT tout import de l'application (comme les autres
# tests) : ce fichier ne doit jamais écrire dans la base de développement,
# même lancé seul.
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.display_state import (
    effective_wired_display_mode,
    report_external_displays,
    reset_hardware_state,
)


def test_mode_effectif_auto_derive_du_materiel():
    assert effective_wired_display_mode("auto", 1) == "dual_screen"
    assert effective_wired_display_mode("auto", 3) == "dual_screen"
    assert effective_wired_display_mode("auto", 0) == "headless"


def test_mode_effectif_auto_sans_rapport_materiel_utilise_le_defaut():
    assert effective_wired_display_mode("auto", None) == "headless"
    assert effective_wired_display_mode("auto", None, default="dual_screen") == "dual_screen"


def test_un_forcage_manuel_l_emporte_toujours_sur_le_materiel():
    assert effective_wired_display_mode("headless", 2) == "headless"
    assert effective_wired_display_mode("dual_screen", 0) == "dual_screen"
    assert effective_wired_display_mode("dual_screen", None) == "dual_screen"


def test_rapport_identique_n_est_pas_un_changement():
    reset_hardware_state()
    assert report_external_displays(1, "windows") is True
    assert report_external_displays(1, "windows") is False
    assert report_external_displays(0, "windows") is True
    assert report_external_displays(-5, "windows") is False  # borné à 0


@pytest.fixture()
def client():
    reset_hardware_state()
    with TestClient(app) as c:
        # Réglage propre : mode auto.
        c.put("/api/settings", json={"display_mode_setting": "auto"})
        from app.database import SessionLocal
        from app.models import Setting
        db = SessionLocal()
        db.query(Setting).filter(Setting.key.in_(["display_output_cable", "display_output_network"])).delete(synchronize_session=False)
        db.commit()
        db.close()
        yield c
    reset_hardware_state()


def test_brancher_puis_debrancher_un_projecteur_change_le_mode_sans_reglage_manuel(client):
    assert client.put("/api/display/state", json={"external_count": 1, "source": "linux"}).json()["wired_display_mode"] == "dual_screen"
    assert client.get("/api/settings").json()["wired_display_mode"] == "dual_screen"
    assert client.get("/api/settings").json()["display_external_count"] == 1
    assert client.put("/api/display/state", json={"external_count": 0, "source": "linux"}).json()["wired_display_mode"] == "headless"
    assert client.get("/api/settings").json()["wired_display_mode"] == "headless"


def test_le_forcage_manuel_survit_aux_rapports_materiels(client):
    client.put("/api/settings", json={"display_mode_setting": "headless"})
    out = client.put("/api/display/state", json={"external_count": 2, "source": "windows"}).json()
    assert out["wired_display_mode"] == "headless"
    assert out["external_count"] == 2
    client.put("/api/settings", json={"display_mode_setting": "auto"})
    assert client.get("/api/settings").json()["wired_display_mode"] == "dual_screen"


def test_un_ancien_client_qui_ecrit_wired_display_mode_force_le_mode(client):
    client.put("/api/display/state", json={"external_count": 0, "source": "linux"})
    client.put("/api/settings", json={"wired_display_mode": "dual_screen"})
    data = client.get("/api/settings").json()
    assert data["display_mode_setting"] == "dual_screen"
    assert data["wired_display_mode"] == "dual_screen"


def test_validation_des_valeurs(client):
    assert client.put("/api/settings", json={"display_mode_setting": "nimporte"}).status_code == 400
    assert client.put("/api/display/state", json={"external_count": -1}).status_code == 422
    assert client.put("/api/display/state", json={"external_count": 99}).status_code == 422


def test_sortie_cable_par_defaut_cinema_en_dual_screen(client):
    # En headless (0 écran externe), la sortie câble par défaut est kiosk
    client.put("/api/display/state", json={"external_count": 0, "source": "linux"})
    assert client.get("/api/settings/display-output").json()["cable"] == "kiosk"

    # En dual_screen (1 écran externe branché), la sortie câble par défaut est cinema
    client.put("/api/display/state", json={"external_count": 1, "source": "linux"})
    assert client.get("/api/settings/display-output").json()["cable"] == "cinema"

    # Un forçage explicite sur le canal câble est respecté
    client.put("/api/settings/display-output", json={"channel": "cable", "output": "kiosk"})
    assert client.get("/api/settings/display-output").json()["cable"] == "kiosk"
