# Assistant d'installation Bobine

Application graphique (poste admin) qui **localise le mini PC**, s'y **connecte
en SSH**, **détecte le matériel**, puis **déroule `install.sh`** avec une barre
de progression en temps réel.

## État

- **`core/` — bibliothèque `bobine-installer-core`** : livrée. Logique **pure**
  et testable (aucune E/S), fondation de l'IHM. Couverte par `cargo test`.
- **`src-tauri/` + `ui/` — Application graphique Tauri 2** : livrée et multi-plateforme.
  Fonctionne nativement sur **Linux** (WebKitGTK), **Windows** (WebView2) et **macOS** (WebKit).
  Scan `/24` complet du sous-réseau (tous les appareils qui répondent, pas
  seulement les cibles Bobine — voir §Scan réseau), authentification SSH par
  mot de passe, agent, clés `~/.ssh/` usuelles ou clé importée explicitement,
  et terminal live PTY.

> `core` ne réimplémente pas l'installation : `install.sh` reste la **source de
> vérité unique**. L'assistant l'**orchestre** (construit la commande, parse sa
> sortie).

## Modules de `core`

| Module | Rôle | Réf. cahier |
|---|---|---|
| `progress` | Parse `install.sh --progress=json` (évènements typés) + `ProgressState` prêt à afficher (barre, libellé, phase, erreur). | §10 |
| `orchestrate` | Construit la commande distante `install.sh` (`sudo` ou `su - --as-user`), sans jamais embarquer de mot de passe. | §7, §10 |
| `privilege` | Arbre de décision de l'amorçage des privilèges (sudo présent ? sudoer ?) → `sudo` vs option B `su -`. | §7 |
| `discovery` | Arithmétique du `/24` à sonder + modèle de candidat + indice d'OS depuis la bannière SSH ou, à défaut, les ports ouverts. | §6 |

## Tester et compiler

```bash
# 1. Lancer la suite de tests unitaires
cd assistant
cargo test --workspace

# 2. Compiler et lancer l'application sous Linux
./build_linux.sh
./target/release/bobine-assistant

# 3. Lancer en mode développement Tauri
npx @tauri-apps/cli dev
```

Le test d'intégration [`core/tests/replay_fixture.rs`](core/tests/replay_fixture.rs)
rejoue un flux `--progress=json` **réel** capturé depuis `install.sh`
([`fixtures/install-events.jsonl`](core/tests/fixtures/install-events.jsonl)) :
garde-fou contre toute divergence entre l'émetteur et le parseur.

## Scan réseau

Le bouton « Lancer le scan réseau » sonde le `/24` de **chaque interface
locale active** (Wi-Fi, Ethernet, VPN...) et affiche **tous les appareils qui
répondent**, pas seulement les cibles Debian/Bobine — un routeur, une
imprimante réseau ou un poste Windows apparaissent aussi, avec leur IP, leur
nom d'hôte résolu (DNS inverse, fonctionne pour les noms `.local` sur la
plupart des systèmes), un indice d'OS et la liste des ports ouverts détectés.
Un appareil est retenu dès qu'**un seul** signal répond (SSH, Bobine, un port
usuel comme HTTP/HTTPS/Samba/RDP/AirPlay/impression réseau, ou même une
simple connexion *refusée* sur un port fermé — preuve qu'un système existe à
cette adresse même sans service exposé). Les résultats sont triés avec les
cibles Bobine/Debian en tête, mais rien n'est filtré : un utilisateur qui
prépare un déploiement headless voit le réseau tel qu'il est réellement,
plutôt qu'une liste tronquée qui pourrait laisser croire à un scan cassé.

En aperçu navigateur autonome (sans backend Tauri, `assistant-ui` dans
`.claude/launch.json`), `app.js` retombe sur un jeu de données factice
utilisant volontairement la plage documentaire réservée RFC 5737
(`203.0.113.0/24`) — jamais une IP privée plausible — et affiche un bandeau
d'avertissement permanent en haut de l'écran, pour qu'un résultat de
démonstration ne puisse jamais être confondu avec un vrai scan réseau.

## Authentification SSH

`authenticate_session` (`src-tauri/src/commands/ssh_auth.rs`) essaie, dans
l'ordre : la clé importée explicitement (bouton « Importer une clé SSH », un
sélecteur de fichier natif via `tauri-plugin-dialog`), le mot de passe saisi
(direct puis clavier-interactif/PAM), l'agent SSH local, puis les clés
usuelles de `~/.ssh/` (`id_ed25519`, `id_rsa`, `id_ecdsa`...). Le mot de passe
sert aussi de passphrase de déchiffrement si la clé importée en réclame une.
Aucun mot de passe ni contenu de clé n'est jamais journalisé.

## Compatibilité Linux, Windows & macOS

L'Assistant d'installation est conçu pour s'exécuter directement depuis le poste de l'administrateur, quel que soit son système d'exploitation :
- **Linux** : binaire natif GTK3/WebKitGTK, exécutable autonome ou paquet `.deb` via `assistant/build_linux.sh`.
- **Windows** : exécutable `.exe` / installateur `.msi` via `npx @tauri-apps/cli build`.
- **macOS** : bundle `.app` / image disque `.dmg` via `npx @tauri-apps/cli build`.
