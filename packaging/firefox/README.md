# Kiosque Firefox (optionnel)

Le kiosque de référence de Bobine reste **Chromium** (appliance headless, voir
`install.sh`). Pour un poste qui doit afficher `/kiosk` ou `/cinema` avec
**Firefox**, ce dossier fournit la politique d'entreprise correspondante.

`policies.json` :
- autorise la lecture automatique **avec son** pour l'interface Bobine locale
  (sans cela Firefox bloque l'audio tant qu'aucun geste n'a eu lieu — il n'y a ni
  souris ni doigt sur un écran câblé) ; tous les autres sites restent en
  « bloquer l'audio » ;
- désactive télémétrie, études, pages de bienvenue et recommandations.

## Installation

| Système | Emplacement du fichier |
|---|---|
| Linux (`.deb`, archive Mozilla) | `/etc/firefox/policies/policies.json` ou `<dossier Firefox>/distribution/policies.json` |
| Linux (snap) | `/etc/firefox/policies/policies.json` (relu par le snap) |
| Windows | `C:\Program Files\Mozilla Firefox\distribution\policies.json` |
| macOS | `/Applications/Firefox.app/Contents/Resources/distribution/policies.json` |

Adaptez la liste `Allow` si votre serveur utilise un autre nom ou port (ce fichier ne prévoit que le port 8000 : si Bobine a pris un port de repli, ajoutez-le). Lancer
ensuite par exemple : `firefox --kiosk http://localhost:8000/kiosk`.
Vérification : `about:policies` doit lister les politiques actives.

Firefox est une marque de la Mozilla Foundation, citée ici sans affiliation.
