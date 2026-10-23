import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../../packaging/storage/49-bobine-storage.rules.in", import.meta.url), "utf8").replaceAll("@BOBINE_USER@", "bobine-test");
let rule;
vm.runInNewContext(source, { polkit: { Result: { YES: "yes", NOT_HANDLED: "unhandled" }, addRule: (callback) => { rule = callback; } } });
const decide = (id, user = "bobine-test", removable = "true") => rule({ id: `org.freedesktop.udisks2.${id}`, lookup: () => removable }, { user });
for (const action of ["filesystem-mount", "modify-device", "modify-device-other-seat", "filesystem-unmount-others", "filesystem-take-ownership", "power-off-drive", "ata-smart-update", "ata-standby"]) {
  assert.equal(decide(action), "yes", action);
  assert.equal(decide(action, "other-user"), "unhandled", action);
  assert.equal(decide(action, "bobine-test", null), "unhandled", action);
  assert.equal(decide(action, "bobine-test", "false"), "unhandled", action);
}
for (const action of ["modify-device-system", "filesystem-mount-system", "open-device", "ata-secure-erase", "manage-swapspace", "loop-setup", "nvme-sanitize", "modify-system-configuration", "unknown"]) {
  assert.equal(decide(action), "unhandled", action);
}
console.log("Politique stockage : compte, support amovible, refus des actions système vérifiés.");
