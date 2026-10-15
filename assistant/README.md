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

| Module | Rôle |
|---|---|
| `progress` | Parse `install.sh --progress=json` (évènements typés) + `ProgressState` prêt à afficher (barre, libellé, phase, erreur). |
| `orchestrate` | Construit la commande distante `install.sh` (`sudo` ou `su - --as-user`), sans jamais embarquer de mot de passe. |
| `privilege` | Arbre de décision de l'amorçage des privilèges (sudo présent ? sudoer ?) → `sudo` vs option B `su -`. |
| `discovery` | Arithmétique du `/24` à sonder + modèle de candidat + indice d'OS depuis la bannière SSH ou, à défaut, les ports ouverts. |

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

Le bouton « Lancer le scan réseau » sonde le réseau de **chaque interface
locale active** (Wi-Fi, Ethernet...), avec son **vrai masque** (de /24 jusqu'à
/22 ; un réseau plus vaste est ramené au bloc /22 du poste) — plus un `/24`
supposé qui ratait la borne sur un réseau /23 ou /22. Les interfaces de
conteneurs/VM, l'auto-adressage 169.254/16 et — tant qu'une autre interface
existe — les tunnels VPN sont ignorés. Les appareils apparaissent **en direct**
(évènements `scan_device`/`scan_progress`) et affiche **tous les appareils qui
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

Robustesse du balayage :

- **Sockets plafonnées** (96 simultanées, tous hôtes confondus) : l'ancien
  balayage ouvrait ~700 sockets d'un coup, au-delà de la limite d'un processus
  graphique macOS (256) — `connect` échouait en « Too many open files », lu
  comme « port fermé », et le scan ne trouvait alors rien, sans erreur.
- **Table ARP** (`/proc/net/arp`, `arp -a`) lue après le balayage : révèle les
  appareils dont tous les ports sont filtrés et fournit l'adresse MAC.
- **Nom `bobine.local`** résolu par le système : trouve la borne même hors des
  réseaux balayés (relais mDNS) ; `/api/health` confirme qu'un port 8000 est
  bien un backend Bobine et non un serveur de dev quelconque.
- **« Scanner un autre réseau »** (`192.168.2.0/24`) pour un VLAN, un réseau
  invité ou un second routeur ; l'état vide liste les causes usuelles
  (borne éteinte, autre réseau, isolation des clients du Wi-Fi).

## Installation sur la cible

`install.sh` est **embarqué à la compilation** (`include_str!`), téléversé par
SCP dans `/tmp` puis lancé via `bash` (`/tmp` peut être monté `noexec`) : la
borne n'a besoin ni de `git`, ni de `curl`, ni d'un dépôt déjà cloné. Le script
s'amorce lui-même (voir l'en-tête d'`install.sh`) : il récupère la version du
canal choisi puis se relance depuis ce dépôt. L'hôte peut être une IP **ou un
nom** (`bobine.local`) — l'ancien code n'acceptait que des IP littérales. La
session SSH envoie des messages de maintien de connexion pendant les étapes
silencieuses (compilation du frontend), et le code de sortie réel d'`install.sh`
est vérifié : un échec est désormais affiché (carte « L'installation n'a pas
abouti » avec « Réessayer » et « Copier le journal »).

En aperçu navigateur autonome (sans backend Tauri, `assistant-ui` : serveur statique
sur `assistant/src`), `app.js` retombe sur un jeu de données factice
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
