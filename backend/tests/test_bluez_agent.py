import asyncio

import pytest

pytest.importorskip("dbus_fast")

from dbus_fast import DBusError

from app.devices.linux.agent import make_agent


class FakeDriver:
    def __init__(self, accept: bool):
        self.accept = accept
        self.cleared = 0
        self.asked = []
        self._pending_future = None

    def _clear_pending(self):
        self.cleared += 1

    async def _device_label(self, device):
        return "AA:BB", "Enceinte"

    async def _agent_confirm(self, address, name, kind, passkey):
        self.asked.append((address, name, kind, passkey))
        return self.accept


def _call(agent, name, *args):
    return getattr(type(agent), name).__wrapped__(agent, *args)


def test_agent_relays_confirmation_and_rejects_refusals():
    accepted, refused = FakeDriver(True), FakeDriver(False)
    asyncio.run(_call(make_agent(accepted), "RequestConfirmation", "/dev", 42))
    assert accepted.asked == [("AA:BB", "Enceinte", "confirm", "000042")]
    with pytest.raises(DBusError):
        asyncio.run(_call(make_agent(refused), "RequestAuthorization", "/dev"))


def test_agent_release_and_cancel_reach_the_driver():
    driver = FakeDriver(True)
    agent = make_agent(driver)
    _call(agent, "Release")
    loop = asyncio.new_event_loop()
    driver._pending_future = loop.create_future()
    _call(agent, "Cancel")
    assert driver.cleared == 1 and driver._pending_future.result() is False
    loop.close()
