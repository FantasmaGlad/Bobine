# Bobine 5.0.3 — Lot d’optimisation Canary

[English](performance-5.0.3.en.md)

Ce lot est destiné au **canal de mise à jour Canary**. La dernière version Stable reste **5.0.2**. Une construction réussie en CI ne remplace pas les essais sur les appareils ; les validations matérielles ci-dessous restent nécessaires avant une promotion Stable.

## Changements

- **Paquets Linux et macOS** : retrait des symboles de débogage lors de la construction PyInstaller. Sur macOS, cette étape précède la signature du bundle.
- **Bibliothèques radio, playlists et cours audio** : chargement groupé des relations SQL, pour supprimer les requêtes répétées par élément dans les listes et détails concernés.
- **Clients du réseau local** : compression gzip des réponses JSON/texte et des fichiers texte du frontend. Les flux audio/vidéo, requêtes Range/HEAD, téléchargements, WebSocket et clients de boucle locale sont exclus. Les variantes statiques conservent des validateurs de cache distincts.
- **Android** : versions de distribution ARM uniquement (`arm64-v8a` pour mobile, `armeabi-v7a` et `arm64-v8a` pour TV). Le développement sur émulateur x86_64 reste disponible avec `./gradlew assembleMobileDebug -PbobineEmulator=true`, ou `assembleTvDebug`. Cette option désactive les variantes release/Play.
- **Dépendances embarquées** : exclusion de YAML, watchfiles et des outils Alembic/Mako des paquets de bureau ; retrait d’Alembic/Mako d’Android. `python-dotenv` reste présent sur bureau, car `pydantic-settings` en dépend à l’import. Les migrations SQLite de Bobine restent intégrées au serveur.

## Mesures de développement

Ces mesures proviennent d’un poste Linux de développement. Elles ne décrivent pas les performances d’une tablette ou d’une appliance Wyse.

| Mesure | Avant | Après | Périmètre |
|---|---:|---:|---|
| Liste radio de 5 000 titres : requêtes SQL | 5 001 | 11 | Chargement par lots de 500 relations |
| Même liste : temps médian | 498 ms | 72 ms | Mesure du 20 octobre, accès ORM local ; hors transfert HTTP |
| JSON de 5 000 titres sur le réseau | 1 042 914 octets | 30 519 octets | Client LAN acceptant gzip |
| Frontend texte sur le réseau | 2,75 Mo | 0,77 Mo | 140 fichiers, client LAN acceptant gzip |
| Dossier PyInstaller Linux : symboles de débogage | 106 Mo | 77 Mo | Construction comparative précédente, Python 3.14 ; gain dépendant des bibliothèques présentes |

**Android, comparaison du même code et du même frontend**, avec la configuration initiale (x86_64 et Alembic), puis celle de ce lot :

| APK signé | Avant | Après | Gain |
|---|---:|---:|---:|
| Mobile | 53 714 687 octets | 45 583 102 octets | 15,1 % |
| TV | 75 352 819 octets | 67 342 873 octets | 10,6 % |

Comparaison supplémentaire du 20 octobre, **mêmes sources, frontend et environnement Python 3.14**, avec `strip=True` dans les deux cas : les exclusions de dépendances font passer le dossier Linux de **78 552 616 à 77 154 928 octets** et son archive gzip niveau 6 de **42 289 614 à 41 572 518 octets**. Ce gain est distinct de celui du retrait des symboles ; ce ne sont pas les tailles des `.deb` CI.

Le coût de compression sur Wyse, la mémoire en exploitation et les tailles finales des paquets CI doivent encore être relevés. Aucun chiffre d’un prototype Rust ne fait partie des gains de cette version.

## Validation locale du lot

- Suite backend : **512 tests réussis**, puis **1 test supplémentaire réussi** après mise à disposition du binaire `bobine-devices` dans la copie de validation. Ce dernier vérifie son protocole, sans valider les périphériques Windows/macOS.
- Frontend : **101 tests réussis**, contrôle TypeScript et construction de production réussis.
- Firefox 158, Linux headless : **17/17 vérifications**, dont imports MP4/MKV, adaptation HEVC, lecture et reprise d’un téléversement après coupure réseau.
- Paquet Linux reconstruit : démarrage et réponses `/api/health`, `/api/settings`, interface et liste radio ; lecture vidéo Range `206` sans compression ; JSON et fichiers statiques gzip vérifiés depuis une interface réseau isolée.
- Android : APK mobile/TV release reconstruits et signatures vérifiées ; quatre bundles AAB (mobile/TV, release/Play) construits sans x86_64 ; APK debug d’émulateur contrôlés avec x86_64 et Python embarqué. Une demande de build release avec l’option émulateur est rejetée. Aucun de ces artefacts n’a été installé sur un appareil pendant cette validation.
- Syntaxe Python contrôlée pour compatibilité 3.11. La CI teste le backend sous Python 3.11, 3.12 et 3.13.

Les versions Python et bibliothèques du poste de développement peuvent différer de celles des paquets CI. Les avertissements de dépréciation Pydantic et un avertissement de coroutine non attendue restent présents dans la suite ; ils ne sont pas corrigés par ce lot.

## Conditions avant une version Stable

| Profil | Vérification encore nécessaire |
|---|---|
| Android mobile | Installation/mise à jour signée, démarrage à froid, import, lecture, WebView et sortie HDMI |
| Android TV ARM 32 bits | Installation, import, lecture, télécommande et conservation des données |
| Linux bureau amd64/arm64 | Installation du `.deb` CI, lancement, import, lecture et mise à jour |
| Appliance Wyse | Lecture continue, import, synchronisation des sorties et mesure du coût gzip |
| Windows x64/ARM64 | Installation, lancement du paquet, import, lecture et mise à jour |
| macOS | Signature du bundle après allègement, lancement, import, lecture et mise à jour |

La publication Canary attend les tests backend, le frontend, le banc Firefox, les vérifications de l’installateur et les constructions requises. Les résultats CI sont accessibles dans [GitHub Actions](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml). Le [canal Canary](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) conserve son tag mobile unique.
