"""Exécution de ffmpeg avec suivi de progression."""
import logging
import subprocess
import threading
import time

from app.utils.ffmpeg_binaries import (
    is_missing_tool_error,
    media_subprocess_kwargs,
    missing_tool_error,
    with_nostdin,
)
from app.utils.video_utils.encoders import background_priority_popen_kwargs, lower_process_priority
from app.utils.video_utils.limits import FFMPEG_NORMALIZE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_UPDATE_INTERVAL_SECONDS = 0.5


def _spawn(cmd: list[str]) -> subprocess.Popen:
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                                **media_subprocess_kwargs(), **background_priority_popen_kwargs())
    except OSError as err:
        if is_missing_tool_error(err):
            logger.error(f"ffmpeg ne peut pas être lancé ({cmd[0]}) : {err}")
            raise missing_tool_error("ffmpeg", err) from err
        raise
    lower_process_priority(proc.pid)
    return proc


def _close(stream) -> None:
    if stream:
        try:
            stream.close()
        except Exception as exc:
            logger.debug("ffmpeg : %s", exc)


def _drain_stderr(proc: subprocess.Popen, chunks: list[str]) -> threading.Thread:
    def read() -> None:
        try:
            if proc.stderr:
                chunks.extend(proc.stderr)
        except Exception as exc:
            logger.debug("ffmpeg : %s", exc)
        finally:
            _close(proc.stderr)

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    return thread


class _Progress:
    def __init__(self, job_id: str | None, duration: float | None, update) -> None:
        self.job_id, self.duration, self.update = job_id, duration, update
        self.speed: str | None = None
        self.last = 0.0

    def _eta(self, done: float) -> int | None:
        if not (self.speed and self.speed.endswith("x")):
            return None
        try:
            factor = float(self.speed[:-1])
        except ValueError:
            return None
        return max(0, int((self.duration - done) / factor)) if factor > 0.05 else None

    def feed(self, line: str) -> None:
        if line.startswith("speed="):
            self.speed = line.split("=", 1)[1].strip()
        elif line.startswith("out_time_us=") and time.time() - self.last >= _UPDATE_INTERVAL_SECONDS:
            self.last = time.time()
            try:
                done = int(line.split("=", 1)[1].strip()) / 1_000_000.0
                percent = eta = None
                if self.duration and self.duration > 0:
                    percent = round(min(99.0, done / self.duration * 100.0), 1)
                    eta = self._eta(done)
                self.update(self.job_id, progress_percent=percent, eta_seconds=eta, speed=self.speed)
            except Exception as exc:
                logger.debug("run_ffmpeg_with_progress : %s", exc)
        elif line == "progress=end":
            self.update(self.job_id, progress_percent=100.0, eta_seconds=0)


def _terminate(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        proc.kill()


def _record_speed(encoder_name: str | None, duration: float | None, elapsed: float, width, height) -> None:
    if duration and duration > 0 and encoder_name and elapsed > 0:
        from app.utils.encode_speed_stats import record_speed_sample, resolution_bucket

        record_speed_sample(encoder_name, resolution_bucket(width, height), duration / elapsed)


def run_ffmpeg_with_progress(
    cmd: list[str],
    job_id: str | None,
    duration_seconds: float | None,
    timeout: int = FFMPEG_NORMALIZE_TIMEOUT_SECONDS,
    encoder_name: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> tuple[int, str]:
    """Exécute FFmpeg en sous-processus Popen avec télémétrie en direct."""
    from app.utils.import_jobs import JobCancelledError, is_job_cancelled, register_job_process, unregister_job_process, update_job

    if is_job_cancelled(job_id):
        raise JobCancelledError(f"Job {job_id} annulé avant le démarrage de FFmpeg")
    full_cmd = with_nostdin(cmd)
    if "-progress" not in full_cmd:
        full_cmd.extend(["-progress", "pipe:1", "-nostats"])
    proc = _spawn(full_cmd)
    if job_id:
        register_job_process(job_id, proc)
    stderr_chunks: list[str] = []
    reader = _drain_stderr(proc, stderr_chunks)
    progress = _Progress(job_id, duration_seconds, update_job)
    start_time = time.time()
    try:
        for line in proc.stdout or ():
            if is_job_cancelled(job_id):
                _terminate(proc)
                raise JobCancelledError(f"Job {job_id} annulé par l'utilisateur")
            if line.strip():
                progress.feed(line.strip())
        proc.wait(timeout=max(1.0, float(timeout - (time.time() - start_time))))
    except subprocess.TimeoutExpired:
        proc.kill()
        raise TimeoutError(f"Délai dépassé ({timeout}s) pour FFmpeg")
    finally:
        if job_id:
            unregister_job_process(job_id)
        _close(proc.stdout)
        reader.join(timeout=1.0)
    stderr_text = "".join(stderr_chunks)
    if proc.returncode != 0:
        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé par l'utilisateur")
        return proc.returncode, stderr_text
    _record_speed(encoder_name, duration_seconds, time.time() - start_time, width, height)
    return 0, stderr_text
