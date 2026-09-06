# Assistant d'installation Bobine

Application graphique (poste admin) qui **localise le mini PC**, s'y **connecte
en SSH**, **détecte le matériel**, puis **déroule `install.sh`** avec une barre
de progression en temps réel.

## État

- **`core/` — bibliothèque `bobine-installer-core`** : livrée. Logique **pure**
  et testable (aucune E/S), fondation de l'IHM. Couverte par `cargo test`.
- **`src-tauri/` + `ui/` — Application graphique Tauri 2** : livrée et multi-plateforme.
  Fonctionne nativement sur **Linux** (WebKitGTK), **Windows** (WebView2) et **macOS** (WebKit).
  Scan `/24` du sous-réseau, diagnostic SSH et terminal live PTY.

> `core` ne réimplémente pas l'installation : `install.sh` reste la **source de
> vérité unique**. L'assistant l'**orchestre** (construit la commande, parse sa
> sortie).

## Modules de `core`

| Module | Rôle | Réf. cahier |
|---|---|---|
| `progress` | Parse `install.sh --progress=json` (évènements typés) + `ProgressState` prêt à afficher (barre, libellé, phase, erreur). | §10 |
| `orchestrate` | Construit la commande distante `install.sh` (`sudo` ou `su - --as-user`), sans jamais embarquer de mot de passe. | §7, §10 |
| `privilege` | Arbre de décision de l'amorçage des privilèges (sudo présent ? sudoer ?) → `sudo` vs option B `su -`. | §7 |
| `discovery` | Arithmétique du `/24` à sonder + modèle de candidat + indice d'OS depuis la bannière SSH. | §6 |

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

## Compatibilité Linux, Windows & macOS

L'Assistant d'installation est conçu pour s'exécuter directement depuis le poste de l'administrateur, quel que soit son système d'exploitation :
- **Linux** : binaire natif GTK3/WebKitGTK, exécutable autonome ou paquet `.deb` via `assistant/build_linux.sh`.
- **Windows** : exécutable `.exe` / installateur `.msi` via `npx @tauri-apps/cli build`.
- **macOS** : bundle `.app` / image disque `.dmg` via `npx @tauri-apps/cli build`.
