import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest

from app.api.errors import error_body
from app.main import app
from app.reference.api import api_reference


@pytest.mark.parametrize(("status", "code"), [(501, "not_implemented"), (502, "bad_gateway")])
def test_device_statuses_have_a_documented_code(status, code):
    assert error_body(status, "Fonction absente.")["code"] == code
    assert api_reference(app.openapi())["errors"]["codes"][str(status)] == code


def test_a_device_error_keeps_its_own_code():
    assert error_body(501, {"code": "unsupported", "message": "Pas de Bluetooth."})["code"] == "unsupported"

