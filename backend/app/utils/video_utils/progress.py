"""Exécution de ffmpeg avec suivi de progression."""
import subprocess
import logging
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
    from app.utils.import_jobs import register_job_process, unregister_job_process, is_job_cancelled, update_job, JobCancelledError
    import threading

    if is_job_cancelled(job_id):
        raise JobCancelledError(f"Job {job_id} annulé avant le démarrage de FFmpeg")

    full_cmd = with_nostdin(cmd)
    if "-progress" not in full_cmd:
        full_cmd.extend(["-progress", "pipe:1", "-nostats"])

    try:
        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            **media_subprocess_kwargs(),
            **background_priority_popen_kwargs(),
        )
    except OSError as err:
        if is_missing_tool_error(err):
            logger.error(f"ffmpeg ne peut pas être lancé ({full_cmd[0]}) : {err}")
            raise missing_tool_error("ffmpeg", err) from err
        raise
    lower_process_priority(proc.pid)
    if job_id:
        register_job_process(job_id, proc)

    stderr_chunks: list[str] = []

    def _read_stderr():
        try:
            if proc.stderr:
                for s_line in proc.stderr:
                    stderr_chunks.append(s_line)
        except Exception:
            pass
        finally:
            if proc.stderr:
                try:
                    proc.stderr.close()
                except Exception:
                    pass

    t_err = threading.Thread(target=_read_stderr, daemon=True)
    t_err.start()

    last_update = 0.0
    current_speed = None
    start_time = time.time()

    try:
        if proc.stdout:
            for line in proc.stdout:
                if is_job_cancelled(job_id):
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    raise JobCancelledError(f"Job {job_id} annulé par l'utilisateur")

                line = line.strip()
                if not line:
                    continue

                if line.startswith("speed="):
                    current_speed = line.split("=", 1)[1].strip()
                elif line.startswith("out_time_us="):
                    now = time.time()
                    if now - last_update >= 0.5:
                        last_update = now
                        try:
                            out_us = int(line.split("=", 1)[1].strip())
                            out_sec = out_us / 1_000_000.0
                            pct = None
                            eta = None
                            if duration_seconds and duration_seconds > 0:
                                pct = round(min(99.0, (out_sec / duration_seconds) * 100.0), 1)
                                if current_speed and current_speed.endswith("x"):
                                    try:
                                        spd_val = float(current_speed[:-1])
                                        if spd_val > 0.05:
                                            eta = max(0, int((duration_seconds - out_sec) / spd_val))
                                    except ValueError:
                                        pass
                            update_job(job_id, progress_percent=pct, eta_seconds=eta, speed=current_speed)
                        except Exception:
                            pass
                elif line == "progress=end":
                    update_job(job_id, progress_percent=100.0, eta_seconds=0)

        remaining_timeout = max(1.0, float(timeout - (time.time() - start_time)))
        proc.wait(timeout=remaining_timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise TimeoutError(f"Délai dépassé ({timeout}s) pour FFmpeg")
    finally:
        if job_id:
            unregister_job_process(job_id)
        if proc.stdout:
            try:
                proc.stdout.close()
            except Exception:
                pass
        t_err.join(timeout=1.0)

    stderr_text = "".join(stderr_chunks)
    if proc.returncode != 0:
        if is_job_cancelled(job_id):
            raise JobCancelledError(f"Job {job_id} annulé par l'utilisateur")
        return (proc.returncode, stderr_text)

    if duration_seconds and duration_seconds > 0 and encoder_name:
        elapsed = time.time() - start_time
        if elapsed > 0:
            from app.utils.encode_speed_stats import record_speed_sample, resolution_bucket

            record_speed_sample(encoder_name, resolution_bucket(width, height), duration_seconds / elapsed)

    return (0, stderr_text)
