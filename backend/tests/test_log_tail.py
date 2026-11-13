from app.api.routes.logs import _tail


def test_tail_returns_last_lines_across_blocks(tmp_path):
    path = tmp_path / "technical.log"
    path.write_text("".join(f"ligne {n}\n" for n in range(5000)), encoding="utf-8")
    assert _tail(path, 3, block=64) == "ligne 4997\nligne 4998\nligne 4999\n"
    assert _tail(path, 10_000, block=1024).count("\n") == 5000


def test_tail_keeps_last_line_without_newline(tmp_path):
    path = tmp_path / "technical.log"
    path.write_bytes("é\nfin".encode())
    assert _tail(path, 1) == "fin"
    assert _tail(path, 5) == "é\nfin"
