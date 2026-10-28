"""Commands and service tasks must finish cleanup before their loop closes."""
import asyncio
import sys

import pytest

from app.devices.base import DeviceError, NullDriver
from app.devices.linux import run_command
from app.devices.service import DevicesService


def _record_process(monkeypatch):
    original = asyncio.create_subprocess_exec
    processes = []
    started = asyncio.Event()
    async def record(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        started.set()
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", record)
    return processes, started


def test_timed_out_command_is_reaped_and_pipes_are_drained(monkeypatch):
    async def scenario():
        processes, _ = _record_process(monkeypatch)
        with pytest.raises(DeviceError) as error:
            await run_command(sys.executable, "-c", "import time; time.sleep(60)", timeout=0.05)
        assert error.value.code == "timeout"
        assert processes[0].returncode is not None
        assert processes[0].stdout.at_eof() and processes[0].stderr.at_eof()
    asyncio.run(scenario())


def test_cancelled_command_is_reaped_without_converting_cancellation(monkeypatch):
    async def scenario():
        processes, started = _record_process(monkeypatch)
        task = asyncio.create_task(run_command(sys.executable, "-c", "import time; time.sleep(60)"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert processes[0].returncode is not None
        assert processes[0].stdout.at_eof() and processes[0].stderr.at_eof()
    asyncio.run(scenario())


def test_service_waits_for_task_cleanup_before_stopping_driver():
    async def scenario():
        events = []
        started = asyncio.Event()
        class Driver(NullDriver):
            async def stop(self):
                events.append("driver-stopped")
        service = DevicesService(lambda: Driver())
        _ = service.driver
        async def monitor():
            started.set()
            try:
                await asyncio.sleep(60)
            finally:
                await asyncio.sleep(0)
                events.append("monitor-cleaned")
        service._monitor = asyncio.create_task(monitor())
        await started.wait()
        await service.stop()
        assert events == ["monitor-cleaned", "driver-stopped"]
        assert service._monitor is None
    asyncio.run(scenario())
