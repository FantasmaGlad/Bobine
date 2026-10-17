"""Chapitres : formats d'import, validation, API."""

import pytest

from app.utils import chapters as ch


def test_horodatages():
    assert ch.parse_timestamp(90) == 90.0
    assert ch.parse_timestamp("90") == 90.0
    assert ch.parse_timestamp("1:30") == 90.0
    assert ch.parse_timestamp("01:02:03") == 3723.0
    assert ch.parse_timestamp("00:05.500") == 5.5
    assert ch.parse_timestamp("00:05,5") == 5.5
    for bad in ("abc", -5, True, "99:99:99:99"):
        with pytest.raises(ch.ChapterError):
            ch.parse_timestamp(bad)


def test_json_objet_liste_et_titres_localises():
    raw = ch.parse_json('{"version":1,"chapters":[{"start":0,"title":"Echauffement"},{"start":"5:00","title":{"fr":"Cardio","en":"Cardio EN"},"end":"10:00"}]}')
    assert raw[0] == {"start_seconds": 0.0, "end_seconds": None, "title": "Echauffement"}
    assert raw[1]["title"] == "Cardio" and raw[1]["end_seconds"] == 600.0
    assert len(ch.parse_json('[{"time": 12, "name": "A"}]')) == 1


def test_json_invalide():
    for bad in ("{", '{"chapters": 3}', '{"chapters": [1]}', '{"chapters": [{"title": "x"}]}'):
        with pytest.raises(ch.ChapterError):
            ch.parse_json(bad)


def test_vtt_et_texte():
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:05:00.000\nIntro\n\n00:05:00.000 --> 00:10:00.000\nBloc <b>1</b>\n"
    assert [c["title"] for c in ch.parse_vtt(vtt)] == ["Intro", "Bloc 1"]
    texte = "00:00 Introduction\n[05:30] - Cardio\n1:02:10 : Etirements\n"
    parsed = ch.parse_text(texte)
    assert [(c["start_seconds"], c["title"]) for c in parsed] == [(0.0, "Introduction"), (330.0, "Cardio"), (3730.0, "Etirements")]
    with pytest.raises(ch.ChapterError):
        ch.parse_text("pas un chapitre")


def test_parse_any_detecte_le_format():
    assert ch.parse_any('{"chapters":[{"start":1,"title":"A"}]}')[0]["title"] == "A"
    assert ch.parse_any("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nA")[0]["title"] == "A"
    assert ch.parse_any("0:01 A")[0]["title"] == "A"
    with pytest.raises(ch.ChapterError):
        ch.parse_any("   ")


def test_normalize_trie_complete_les_fins_et_valide():
    out = ch.normalize(
        [
            {"start_seconds": 300.0, "end_seconds": None, "title": "B"},
            {"start_seconds": 0.0, "end_seconds": None, "title": "A"},
        ],
        600.0,
    )
    assert [(c["title"], c["start_seconds"], c["end_seconds"]) for c in out] == [("A", 0.0, 300.0), ("B", 300.0, 600.0)]
    with pytest.raises(ch.ChapterError):
        ch.normalize([{"start_seconds": 0.0, "end_seconds": None, "title": " "}], 60.0)
    with pytest.raises(ch.ChapterError):
        ch.normalize([{"start_seconds": 0.0, "end_seconds": None, "title": "A"}, {"start_seconds": 0.0, "end_seconds": None, "title": "B"}], 60.0)
    with pytest.raises(ch.ChapterError):
        ch.normalize([{"start_seconds": 999.0, "end_seconds": None, "title": "A"}], 60.0)
    with pytest.raises(ch.ChapterError):
        ch.normalize([{"start_seconds": float(i), "end_seconds": None, "title": "x"} for i in range(ch.MAX_CHAPTERS + 1)], None)


def test_fin_incoherente_ramenee_au_chapitre_suivant():
    out = ch.normalize(
        [
            {"start_seconds": 0.0, "end_seconds": 900.0, "title": "A"},
            {"start_seconds": 300.0, "end_seconds": None, "title": "B"},
        ],
        600.0,
    )
    assert out[0]["end_seconds"] == 300.0
