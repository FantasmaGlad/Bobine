# Volontairement SANS `from __future__ import annotations` : dbus-fast lit les annotations des
# méthodes comme des signatures D-Bus ("o", "s", "u"...) et ne sait pas interpréter des chaînes différées.
"""Agent d'appairage BlueZ (`org.bluez.Agent1`) : relaie les demandes de confirmation à l'interface."""

from dbus_fast import DBusError
from dbus_fast.service import ServiceInterface, method


def make_agent(driver):
    def rejected():
        return DBusError("org.bluez.Error.Rejected", "Rejected")

    class BobineAgent(ServiceInterface):
        def __init__(self):
            super().__init__("org.bluez.Agent1")

        @method()
        def Release(self):  # noqa: N802 - noms imposés par D-Bus
            driver._clear_pending()

        @method()
        def RequestPinCode(self, device: "o") -> "s":  # noqa: F821
            return "0000"  # code historique des casques et enceintes sans écran

        @method()
        def DisplayPinCode(self, device: "o", pincode: "s"):  # noqa: F821
            return

        @method()
        def RequestPasskey(self, device: "o") -> "u":  # noqa: F821
            return 0

        @method()
        def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):  # noqa: F821
            return

        @method()
        async def RequestConfirmation(self, device: "o", passkey: "u"):  # noqa: F821
            address, name = await driver._device_label(device)
            if not await driver._agent_confirm(address, name, "confirm", f"{passkey:06d}"):
                raise rejected()

        @method()
        async def RequestAuthorization(self, device: "o"):  # noqa: F821
            address, name = await driver._device_label(device)
            if not await driver._agent_confirm(address, name, "authorize", None):
                raise rejected()

        @method()
        def AuthorizeService(self, device: "o", uuid: "s"):  # noqa: F821
            return  # appareil déjà appairé qui demande un profil audio : accepté

        @method()
        def Cancel(self):  # noqa: N802
            future = driver._pending_future
            if future is not None and not future.done():
                future.set_result(False)

    return BobineAgent()
