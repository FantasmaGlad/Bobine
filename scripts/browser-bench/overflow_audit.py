#!/usr/bin/env python3
"""Audit de débordement horizontal : parcourt les pages d'administration à plusieurs largeurs de fenêtre
(celles qu'on obtient avec une barre latérale de navigateur ou des onglets verticaux) et signale tout
élément dont le bord droit dépasse la fenêtre sans être contenu par un conteneur défilant.

Usage :
    BOBINE_URL=http://127.0.0.1:8078 python3 scripts/browser-bench/overflow_audit.py [largeur ...]

Prérequis : geckodriver dans le PATH (`geckodriver --port 4444`), un backend de test ISOLÉ avec quelques
données (jamais vos données réelles), `frontend/out` construit. Code de sortie 0 si aucun dépassement.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geckodriver_client as wd  # noqa: E402

BASE = os.environ.get("BOBINE_URL", "http://127.0.0.1:8078").rstrip("/")
WIDTHS = [int(a) for a in sys.argv[1:]] or [768, 900, 1024, 1180, 1280, 1400]
ROUTES = [
    "/dashboard-cable", "/dashboard-network", "/library", "/playlists", "/schedule", "/audio", "/audio-playlists",
    "/backgrounds", "/radio-library", "/radio-remote", "/radio-announcements", "/metrics/courses",
    "/metrics/system", "/settings", "/logs", "/devices",
]

MEASURE_JS = r"""
const W = window.innerWidth;
const clipped = (el) => {
  for (let p = el.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX;
    // Défilement voulu = un composant (rangée, tableau) qui défile ; la zone de contenu principale qui défile en largeur EST le défaut.
    if ((o === 'auto' || o === 'scroll') && p.tagName !== 'MAIN' && p.getBoundingClientRect().right <= W + 1) return true;
  }
  return false;
};
const offenders = [];
for (const el of document.querySelectorAll('body *')) {
  const cs = getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0 || r.right <= W + 1) continue;
  if (clipped(el)) continue;
  offenders.push((el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '')) + ' → ' + Math.round(r.right) + 'px');
  if (offenders.length >= 6) break;
}
// Contenu coupé par son propre conteneur (overflow caché) : texte tronqué volontairement exclu.
const cut = [];
for (const el of document.querySelectorAll('body *')) {
  const cs = getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden') continue;
  if (cs.overflowX !== 'hidden' && cs.overflowX !== 'clip') continue;
  if (cs.textOverflow === 'ellipsis' || el.scrollWidth <= el.clientWidth + 2) continue;
  // Seul un descendant EN FLUX (non positionné) qui dépasse compte : un décor absolu volontairement débordant est ignoré.
  const box = el.getBoundingClientRect();
  const realOverflow = [...el.querySelectorAll('*')].some((c) => {
    const pos = getComputedStyle(c).position;
    return pos !== 'absolute' && pos !== 'fixed' && c.getBoundingClientRect().right > box.right + 2 && c.getBoundingClientRect().width > 0;
  });
  if (!realOverflow) continue;
  if (el.getBoundingClientRect().width === 0) continue;
  if (el.closest('[aria-hidden="true"], .marquee, [class*="marquee"], .sr-only')) continue;
  cut.push(el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '') + ' → contenu ' + el.scrollWidth + 'px / visible ' + el.clientWidth + 'px');
  if (cut.length >= 6) break;
}
return { width: W, scrollWidth: document.documentElement.scrollWidth, offenders: offenders.concat(cut) };
"""


def main() -> int:
    print("Firefox", wd.start(headless=True, width=WIDTHS[0], height=900), flush=True)
    failures = 0
    try:
        for width in WIDTHS:
            wd.set_window_rect(width, 900)
            for route in ROUTES:
                wd.navigate(f"{BASE}{route}")
                time.sleep(1.3)
                result = wd.execute(MEASURE_JS)
                bad = result["offenders"] or result["scrollWidth"] > result["width"] + 1
                if bad:
                    failures += 1
                    print(f"[DÉPASSEMENT] {width}px {route} — scrollWidth {result['scrollWidth']} / fenêtre {result['width']} — {result['offenders']}", flush=True)
        print(f"{failures} dépassement(s) sur {len(WIDTHS) * len(ROUTES)} mesures", flush=True)
    finally:
        wd.quit_session()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
