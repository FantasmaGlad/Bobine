"use client";

import DashboardScreen from "@/components/DashboardScreen";

/** Tableau de bord du canal RÉSEAU (kiosks ouverts depuis d'autres appareils
 * du LAN). */
export default function DashboardNetworkPage() {
  return <DashboardScreen channel="network" />;
}
