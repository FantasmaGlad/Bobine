import type { SectionProps } from "./common";

/** Libellés d'accessibilité du pavé PIN, tirés du dictionnaire courant. */
export function pinLabels(t: SectionProps["t"]) {
  return {
    group: t("devices.pin.group"),
    delete: t("devices.pin.delete"),
    filled: (count: number, total: number) => t("devices.pin.filled", { count, total }),
  };
}
