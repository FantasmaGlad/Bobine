# Banc de compatibilité navigateurs (Firefox / Gecko)

Outils jetables, sans dépendance (bibliothèque standard Python + JavaScript
injecté), utilisés pour établir les mesures de
compatibilité Firefox. Ils ne font jamais partie du build de Bobine.

| Fichier | Rôle |
|---|---|
| `geckodriver_client.py` | Client WebDriver W3C minimal (pilote Firefox via `geckodriver`). |
| `monitor.js` | Moniteur de réactivité injecté dans la page : retard de la boucle d'évènements (`setInterval` 25 ms) et écarts entre frames (`requestAnimationFrame`) → `window.__mon`. |
| `support-matrix.js` | Matrice de support navigateur : codecs (`canPlayType` / `MediaSource`), API Web, fonctions CSS. |
| `playtest.js` | Lit `arguments[0]` (URL d'un flux) 8 s dans un `<video>` et rapporte images décodées / perdues, état, erreur. |
| `throttle_proxy.py` | Proxy TCP qui limite le débit montant et ajoute de la latence (simule un Wi-Fi de salle). |

## Mise en route

```bash
# 1. Backend de test ISOLÉ (jamais sur vos données réelles) — sans mDNS pour ne
#    rien annoncer sur le réseau :
cd backend
BOBINE_USE_XDG=1 XDG_DATA_HOME=/tmp/bobine-bench/data XDG_CONFIG_HOME=/tmp/bobine-bench/cfg \
  .venv/bin/python -c "
import app.utils.mdns as m; m.start_mdns_responder = lambda port: None
import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=8078, log_level='warning')"

# 2. (optionnel) lien limité à 4 Mo/s, 30 ms :
python3 scripts/browser-bench/throttle_proxy.py 4 30 8079 8078

# 3. geckodriver (Firefox installé en snap : les fichiers à téléverser doivent
#    se trouver dans votre dossier personnel NON caché, pas dans /tmp ni ~/.cache)
geckodriver --port 4444 &
```

```python
import sys; sys.path.insert(0, "scripts/browser-bench")
import geckodriver_client as wd
print(wd.start(headless=True))                    # version de Firefox
wd.navigate("http://127.0.0.1:8078/library/")
wd.execute(open("scripts/browser-bench/monitor.js").read())
wd.send_keys(wd.find("input[type=file]"), "/home/vous/medias/a.mp4\n/home/vous/medias/b.mp4")
# ... cliquer « Lancer N uploads », puis relire window.__mon
print(wd.execute("return window.__mon"))
print(wd.execute(open("scripts/browser-bench/support-matrix.js").read()))
```

## Limites connues du banc

- Firefox **headless**, sans accélération GPU : pire cas réaliste pour un poste
  sans décodage matériel, mais pas représentatif d'un poste équipé.
- Linux uniquement ; Windows, macOS et Firefox pour Android restent à mesurer.
- Fichiers synthétiques (`ffmpeg -f lavfi -i testsrc2`) : pas de contenu réel.
- `performance.now()` est dégradé par `privacy.resistFingerprinting`
  (Tor Browser, LibreWolf) : les retards inférieurs à 100 ms n'y sont pas fiables.
