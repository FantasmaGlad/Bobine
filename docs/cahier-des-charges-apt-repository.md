# Cahier des Charges — Dépôt APT Officiel Bobine (`apt.bobine.fit`)

## 1. Contexte & Objectifs

Actuellement, l'installation de Bobine sur les systèmes Linux Desktop (Debian, Ubuntu, Linux Mint) repose sur le téléchargement manuel de fichiers `.deb` isolés depuis GitHub Releases.

Bien que fonctionnelle, cette méthode présente trois limites majeures :
1. **Absence de mises à jour automatiques** : L'utilisateur ne bénéficie pas des commandes standard `sudo apt update && sudo apt upgrade`.
2. **Gestion manuelle des dépendances** : Un paquet `.deb` installé via un double-clic ou `dpkg -i` peut échouer si des dépendances système (`ffmpeg`, `avahi-daemon`) ne sont pas déjà présentes dans le cache local.
3. **Segmentation des canaux (Stable / Bêta)** : L'utilisateur ne peut pas basculer facilement de canal sans retélécharger manuellement une archive.

### Objectifs du projet
- Fournir un **dépôt APT officiel, signé cryptographiquement par GPG**, conforme aux standards Debian modernes (Debian 12 Bookworm, Debian 13 Trixie, Ubuntu 22.04 LTS, Ubuntu 24.04 LTS).
- Intégrer les deux canaux de distribution :
  - `stable` : versions officielles figées (tags `Vx.y.z`).
  - `beta` : versions préliminaires roulantes (tag `beta`).
- Automatiser la publication du dépôt directement dans le pipeline CI/CD GitHub Actions existant (`.github/workflows/ci.yml`).
- Héberger le dépôt à coût nul et haute disponibilité via **GitHub Pages** sous le domaine personnalisé **`https://apt.bobine.fit/`** (avec proxy et CDN Cloudflare).
- Permettre à tout utilisateur d'installer Bobine en 3 commandes simples :
  ```bash
  curl -fsSL https://apt.bobine.fit/bobine.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/bobine.gpg
  echo "deb [signed-by=/etc/apt/keyrings/bobine.gpg] https://apt.bobine.fit/ stable main" | sudo tee /etc/apt/sources.list.d/bobine.list
  sudo apt update && sudo apt install bobine
  ```

---

## 2. Architecture Technique & Choix d'Outils

### A. Générateur de Dépôt : `reprepro`
`reprepro` est l'outil de référence au sein de l'écosystème Debian pour créer et administrer des dépôts APT statiques :
- Il gère automatiquement les arborescences `pool/main/...` et `dists/<distribution>/...`.
- Il extrait les métadonnées de contrôle des paquets `.deb` et génère les index compressés `Packages.gz`.
- Il signe numériquement les fichiers d'index (`InRelease` pour la signature intégrée, `Release.gpg` pour la signature détachée).
- Il supporte plusieurs distributions au sein d'un même dépôt (`stable` et `beta`).

### B. Hébergement & Réseau : GitHub Pages + Cloudflare
- **Stockage** : Branche dédiée `gh-pages` sur le dépôt `FantasmaGlad/Bobine`.
- **Nom de domaine** : `apt.bobine.fit` configuré via un fichier `CNAME` à la racine de la branche.
- **Routage DNS (Cloudflare)** :
  - Type : `CNAME`
  - Nom : `apt`
  - Cible : `fantasmaglad.github.io`
  - Proxy : Activé (nuage orange, mise en cache CDN des paquets `.deb` et des métadonnées).
- **Sécurité SSL/TLS** : Cloudflare gère la terminaison SSL en mode Full (Strict) avec HTTP/3 et 0-RTT.

### C. Signature Cryptographique GPG
- **Type de clé** : RSA 4096 bits.
- **Identité** : `Bobine APT Repository <contact@bobine.fit>`.
- **Emplacement des secrets** :
  - `APT_GPG_PRIVATE_KEY` : Clé privée blindée au format ASCII armor stockée dans les *GitHub Actions Secrets*.
  - `APT_GPG_PASSPHRASE` : Passphrase de protection de la clé privée (optionnelle si clé sans mot de passe dédiée à la CI).
- **Distribution de la clé publique** : Accessible publiquement à l'adresse `https://apt.bobine.fit/bobine.gpg`.

---

## 3. Structure de l'Arborescence du Dépôt Statique

La branche `gh-pages` contiendra la structure suivante :

```
apt.bobine.fit/
├── CNAME                                  # apt.bobine.fit
├── index.html                             # Page d'accueil sobre expliquant la commande d'installation
├── bobine.gpg                             # Clé publique GPG du dépôt
├── conf/                                  # Configuration reprepro (utilisée par la CI)
│   ├── distributions
│   └── options
├── pool/                                  # Stockage des fichiers .deb réels
│   └── main/
│       └── b/
│           └── bobine/
│               ├── bobine_3.0.0_amd64.deb
│               └── bobine_3.0.1~beta_amd64.deb
└── dists/                                 # Métadonnées d'indexation APT
    ├── stable/
    │   ├── InRelease                      # Index signé (format moderne)
    │   ├── Release                        # Index des sommes SHA256
    │   ├── Release.gpg                    # Signature détachée
    │   └── main/
    │       └── binary-amd64/
    │           ├── Packages
    │           ├── Packages.gz
    │           └── Release
    └── beta/
        ├── InRelease
        ├── Release
        ├── Release.gpg
        └── main/
            └── binary-amd64/
                ├── Packages
                ├── Packages.gz
                └── Release
```

---

## 4. Spécifications de Configuration `reprepro`

Fichier `conf/distributions` :

```text
Origin: Bobine
Label: Bobine
Suite: stable
Codename: stable
Architectures: amd64
Components: main
Description: Depot officiel Bobine - Canal Stable
SignWith: contact@bobine.fit

Origin: Bobine
Label: Bobine
Suite: beta
Codename: beta
Architectures: amd64
Components: main
Description: Depot officiel Bobine - Canal Beta (Rolling)
SignWith: contact@bobine.fit
```

---

## 5. Intégration dans le Pipeline CI/CD (`ci.yml`)

L'intégration viendra s'insérer après les jobs de compilation des paquets `.deb` :

### A. Publication Stable (`release-stable`)
- **Condition** : Tag `Vx.y.z` poussé sur le dépôt.
- **Actions** :
  1. Récupération de l'artefact `bobine-linux-deb`.
  2. Clonage de la branche `gh-pages`.
  3. Import de la clé GPG privée depuis les secrets GitHub.
  4. Exécution de :
     ```bash
     reprepro -b apt-repo includedeb stable dist-deb/*.deb
     ```
  5. Commit et push sur `gh-pages`.

### B. Publication Bêta (`release-beta`)
- **Condition** : Déclenchement manuel avec `publish_beta: true`.
- **Actions** :
  1. Récupération de l'artefact `bobine-linux-deb` (portant la version `x.y.z~beta`).
  2. Suppression de l'ancienne version bêta dans reprepro :
     ```bash
     reprepro -b apt-repo remove beta bobine
     ```
  3. Ajout de la nouvelle version bêta :
     ```bash
     reprepro -b apt-repo includedeb beta dist-deb/*.deb
     ```
  4. Commit et push sur `gh-pages`.

---

## 6. Guide Consommateur & Rétrocompatibilité

### Format Moderne DEB822 (Ubuntu 24.04 / Debian 13)
```text
Types: deb
URIs: https://apt.bobine.fit/
Suites: stable
Components: main
Signed-By: /etc/apt/keyrings/bobine.gpg
```

### Format Traditionnel (Ubuntu 20.04 / 22.04 / Debian 11 / 12)
```text
deb [signed-by=/etc/apt/keyrings/bobine.gpg] https://apt.bobine.fit/ stable main
```

Pour basculer sur le canal **Bêta**, l'utilisateur remplace simplement `stable` par `beta` dans sa source APT.
