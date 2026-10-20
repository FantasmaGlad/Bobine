"""Exercise transport failures against real, disposable stdlib subprocesses."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import textwrap
import time

import pytest

from app.utils import media_sidecar as media


@pytest.fixture
def child_factory(tmp_path, monkeypatch):
    script = tmp_path / "fake media worker.py"
    script.write_text(textwrap.dedent('''
        import base64, json, os, sys, time
        mode = sys.argv[1]
        for line in sys.stdin:
            request = json.loads(line)
            method = request['method']
            path = request['params'].get('path', '')
            if method == 'hello':
                if mode == 'hello_timeout': time.sleep(5)
                if mode == 'hello_delay': time.sleep(.12)
                if mode == 'blocked_stdin':
                    import fcntl
                    fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETPIPE_SZ, 4096)
                if mode == 'hello_eof': sys.exit(0)
                if mode == 'hello_native':
                    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32001,'message':'private','data':{'reason':'unsupported'}}}), flush=True)
                    continue
                result = {'protocol_version':1,'binary_version':'0.1.0',
                    'profiles':['radio-v1','course-duration-v1'],'formats':['mp3','flac','wav'],
                    'capabilities':{'probe_audio':True,'extract_cover':True,'experimental':True},
                    'limits':{'request_bytes':65536,'response_bytes':8388608,'cover_bytes':4194304}}
                if mode == 'hello_version': result['protocol_version'] = 2
                if mode == 'hello_bool': result['protocol_version'] = True
                if mode == 'hello_limits': result['limits']['cover_bytes'] = True
            elif method == 'probe_audio':
                if path == 'timeout': time.sleep(5)
                if path == 'slow': time.sleep(.30)
                if path == 'small_slow': time.sleep(.12)
                if path == 'crash': sys.exit(7)
                if path == 'eof': sys.exit(0)
                if path == 'oversize':
                    sys.stdout.write('x' * (8388608 + 100)); sys.stdout.flush(); time.sleep(5)
                metadata = {key: None for key in ('title','artist','album','album_artist','track_number','disc_number','year','genre','duration_seconds')}
                metadata.update(title=path, duration_seconds=1.25)
                if path == 'duration_bool': metadata['duration_seconds'] = True
                if path == 'duration_infinite': metadata['duration_seconds'] = float('inf')
                if path == 'duration_negative': metadata['duration_seconds'] = -1
                if path == 'track_bool': metadata['track_number'] = True
                if path == 'missing_key': del metadata['genre']
                if path == 'title_number': metadata['title'] = 10
                if path == 'title_surrogate': metadata['title'] = '\\udcff'
                if path == 'unsupported':
                    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32001,'message':'PRIVATE-PATH-DO-NOT-LOG','data':{'reason':'unsupported'}}}), flush=True)
                    continue
                result = {'status':'ok','profile':request['params']['profile'],'format':'mp3','metadata':metadata}
                if path == 'wrong_profile': result['profile'] = 'wrong'
                if path == 'unadvertised_format': result['format'] = 'wma'
            else:
                if request['params'].get('profile') != 'radio-v1': sys.exit(3)
                cover = None if path == 'absent' else {'mime':'image/png','bytes':3,'data_base64':'YWJj'}
                if path == 'bad_b64': cover['data_base64'] = '!!!!'
                if path == 'bad_size': cover['bytes'] = 2
                if path == 'bad_mime': cover['mime'] = 'text/plain'
                if path == 'huge_cover': cover['bytes'] = 4194305
                if path == 'padding_bits': cover = {'mime':'image/png','bytes':1,'data_base64':'YR=='}
                result = {'status':'ok','cover':cover}
            reply = {'jsonrpc':'2.0','id':request['id'],'result':result}
            if path == 'wrong_id': reply['id'] += 1
            if path == 'bool_id': reply['id'] = True
            if path == 'both': reply['error'] = {'code':-1,'message':'no'}
            if path == 'wrong_jsonrpc': reply['jsonrpc'] = '1.0'
            if path == 'duplicate':
                print('{"jsonrpc":"2.0","id":%s,"id":%s,"result":{}}' % (request['id'], request['id']), flush=True)
            elif path == 'malformed': print('{bad}', flush=True)
            elif mode == 'crlf':
                sys.stdout.write(json.dumps(reply) + chr(13) + chr(10)); sys.stdout.flush()
            else: print(json.dumps(reply), flush=True)
            if method == 'hello' and mode == 'blocked_stdin': time.sleep(5)
    '''))
    clients = []
    children = []
    original = subprocess.Popen

    def record(*args, **kwargs):
        proc = original(*args, **kwargs)
        children.append(proc)
        return proc

    monkeypatch.setattr(media.subprocess, "Popen", record)

    def create(mode="normal", timeout=1.0, enabled=True):
        client = media.MediaClient([sys.executable, "-u", str(script), mode], timeout=timeout, enabled=enabled)
        clients.append(client)
        return client

    yield create, children
    for client in clients:
        client.close()
    assert all(proc.poll() is not None for proc in children), "disposable child was not reaped"


def test_disabled_and_unrepresentable_paths_do_not_spawn(child_factory, monkeypatch):
    create, children = child_factory
    monkeypatch.delenv("BOBINE_MEDIA_NATIVE", raising=False)
    client = create(enabled=None)
    assert client.probe_audio("valid") is None
    assert client.extract_cover("valid") == media.CoverResult(available=False)
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "true")
    assert client.probe_audio("valid") is None
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    for path in ("bad\0name", "bad\udcffname", b"bytes", ""):
        assert client.probe_audio(path) is None
    assert children == []
    assert client.probe_audio("valid")["duration_seconds"] == 1.25


def test_profiles_and_proven_cover_absence_are_distinct(child_factory):
    create, children = child_factory
    client = create()
    assert client.probe_audio(Path("Morceau été.mp3"))["title"] == "Morceau été.mp3"
    assert client.probe_audio("course", "course-duration-v1")["duration_seconds"] == 1.25
    assert client.extract_cover("absent") == media.CoverResult(available=True)
    assert client.extract_cover("present") == media.CoverResult(True, b"abc", "image/png")
    assert len(children) == 1


@pytest.mark.parametrize("mode", ["hello_version", "hello_bool", "hello_limits", "hello_eof", "hello_timeout", "hello_native"])
def test_failed_identification_reaps_child(child_factory, mode):
    create, children = child_factory
    client = create(mode, timeout=.15)
    started = time.monotonic()
    assert client.probe_audio("valid") is None
    assert time.monotonic() - started < 1.5
    assert len(children) == 1 and children[0].returncode is not None


@pytest.mark.parametrize("path", ["wrong_id", "bool_id", "both", "wrong_jsonrpc", "duplicate", "malformed", "duration_bool", "duration_infinite", "duration_negative", "track_bool", "missing_key", "title_number", "title_surrogate", "wrong_profile", "unadvertised_format", "oversize", "crash", "eof", "timeout"])
def test_invalid_or_failed_probe_reaps_and_restarts(child_factory, path):
    create, children = child_factory
    client = create(timeout=.30)
    assert client.probe_audio(path) is None
    assert children[0].returncode is not None
    assert client.probe_audio("recovered")["title"] == "recovered"
    assert len(children) == 2


@pytest.mark.parametrize("path", ["bad_b64", "bad_size", "bad_mime", "huge_cover", "padding_bits"])
def test_cover_protocol_failure_is_not_proven_absence(child_factory, path):
    create, children = child_factory
    client = create()
    assert client.extract_cover(path).available is False
    assert children[0].returncode is not None


def test_native_refusal_preserves_child_and_hides_message(child_factory, caplog):
    create, children = child_factory
    client = create()
    with caplog.at_level("INFO"):
        assert client.probe_audio("unsupported") is None
    assert client.last_failure == "unsupported"
    assert "PRIVATE-PATH" not in caplog.text
    assert client.probe_audio("ok")["title"] == "ok"
    assert len(children) == 1


def test_threads_share_one_process_without_mixing_replies(child_factory):
    create, children = child_factory
    client = create()
    with ThreadPoolExecutor(max_workers=6) as executor:
        names = ["song-%s" % i for i in range(18)]
        results = list(executor.map(client.probe_audio, names))
    assert [result["title"] for result in results] == names
    assert len(children) == 1


def test_waiting_for_serial_lock_consumes_same_deadline(child_factory):
    create, children = child_factory
    client = create(timeout=.45)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(client.probe_audio, "slow")
        time.sleep(.08)
        started = time.monotonic()
        second = executor.submit(client.probe_audio, "slow")
        assert first.result()["title"] == "slow"
        assert second.result() is None
        elapsed = time.monotonic() - started
    assert .30 < elapsed < .80
    assert len(children) == 1 and children[0].returncode is not None


def test_close_interrupts_active_request_and_is_final(child_factory):
    create, children = child_factory
    client = create(timeout=5)
    assert client.probe_audio("ready")
    with ThreadPoolExecutor(max_workers=1) as executor:
        active = executor.submit(client.probe_audio, "timeout")
        time.sleep(.05)
        client.close()
        assert active.result(timeout=1) is None
    assert children[0].returncode is not None
    client.close()
    assert client.probe_audio("later") is None
    assert len(children) == 1


def test_request_limit_and_missing_binary_use_fallback(child_factory, monkeypatch):
    create, children = child_factory
    client = create()
    assert client.probe_audio("x" * media.MAX_REQUEST_BYTES) is None
    assert children[0].returncode is not None
    monkeypatch.setenv("BOBINE_MEDIA_SIDECAR", "/nonexistent component --shell-option")
    assert media.find_binary() is None
    missing = media.MediaClient(enabled=True)
    assert missing.probe_audio("anything") is None
    missing.close()
    assert len(children) == 1


def test_override_is_one_literal_path_and_frozen_environment(tmp_path, monkeypatch):
    executable = tmp_path / "component with spaces"
    executable.write_text("placeholder")
    executable.chmod(0o755)
    monkeypatch.setenv("BOBINE_MEDIA_SIDECAR", str(executable))
    assert media.find_binary() == [str(executable)]
    monkeypatch.setenv("LD_LIBRARY_PATH", "bundled-libraries")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "original-libraries")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert media._child_env()["LD_LIBRARY_PATH"] == "original-libraries"
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    assert "LD_LIBRARY_PATH" not in media._child_env()


def test_handshake_and_probe_share_one_budget(child_factory):
    create, children = child_factory
    client = create("hello_delay", timeout=.20)
    started = time.monotonic()
    assert client.probe_audio("small_slow") is None
    assert time.monotonic() - started < .65
    assert children[0].returncode is not None


@pytest.mark.skipif(sys.platform != "linux", reason="Linux pipe capacity control")
def test_child_not_reading_stdin_cannot_block_caller(child_factory):
    create, children = child_factory
    client = create("blocked_stdin", timeout=.20)
    started = time.monotonic()
    assert client.probe_audio("x" * 60000) is None
    assert time.monotonic() - started < .65
    assert children[0].returncode is not None


def test_explicit_shutdown_closes_stdin_for_clean_eof(child_factory):
    create, children = child_factory
    client = create("crlf")
    assert client.probe_audio("framed")["title"] == "framed"
    client.close()
    assert children[0].returncode == 0


def test_real_native_wave_probe_and_cover_contract(tmp_path):
    import wave
    binary = Path(__file__).resolve().parents[2] / "media" / "target" / "release" / ("bobine-media.exe" if sys.platform == "win32" else "bobine-media")
    if not binary.is_file():
        pytest.skip("native release binary has not been built")
    source = tmp_path / "cours été.wav"
    with wave.open(str(source), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\0\0" * 1600)
    client = media.MediaClient([str(binary)], enabled=True)
    try:
        metadata = client.probe_audio(source, "course-duration-v1")
        assert metadata is not None and abs(metadata["duration_seconds"] - .2) < .001
        assert client.extract_cover(source) == media.CoverResult(available=True)
    finally:
        client.close()
