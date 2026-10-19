"""Historique matériel : périodes longues (30 jours, mois en cours, tout l'historique)."""

import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import SystemMetricsHistory


@pytest.fixture()
def client():
    with TestClient(app) as c:
        db = SessionLocal()
        try:
            db.query(SystemMetricsHistory).delete()
            now = datetime.now(timezone.utc)
            for days_ago in (0, 3, 20, 45):
                db.add(SystemMetricsHistory(timestamp=now - timedelta(days=days_ago), cpu_percent=10.0 + days_ago))
            db.commit()
        finally:
            db.close()
        yield c
        db = SessionLocal()
        try:
            db.query(SystemMetricsHistory).delete()
            db.commit()
        finally:
            db.close()


def _count(client, period):
    response = client.get("/api/metrics/hardware/history", params={"metric": "cpu", "period": period})
    assert response.status_code == 200, response.text
    return len(response.json()["points"])


def test_les_periodes_longues_elargissent_l_historique(client):
    assert _count(client, "1h") == 1
    assert _count(client, "7d") == 2
    assert _count(client, "30d") == 3
    assert _count(client, "all") == 4


def test_ce_mois_ci_commence_au_premier_du_mois(client):
    expected = 1 + sum(1 for d in (3, 20, 45) if (datetime.now(timezone.utc) - timedelta(days=d)).month == datetime.now(timezone.utc).month
                       and (datetime.now(timezone.utc) - timedelta(days=d)).year == datetime.now(timezone.utc).year)
    assert _count(client, "this_month") == expected


def test_une_periode_inconnue_est_refusee(client):
    assert client.get("/api/metrics/hardware/history", params={"metric": "cpu", "period": "1y"}).status_code == 422
