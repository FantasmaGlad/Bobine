# Cahier des charges — Sécurité, intégrité des mises à jour, hygiène des dépendances

> Spécification pour 5 points d'amélioration identifiés le 2026-09-17 :
> zip-slip à l'import ZIP audio/radio, intégrité des mises à jour desktop,
> télémétrie de flotte, Dependabot, cohérence de la documentation agents IA.

---

## 1. Zip-slip à l'import ZIP audio et radio

### Constat

`zipfile.ZipFile.extractall()` extrait chaque membre de l'archive à l'emplacement que SON PROPRE nom de chemin dicte, sans jamais vérifier que ce chemin reste sous le dossier de destination — une archive contenant une entrée nommée `../../../etc/cron.d/x` (ou équivalent Windows) écrit hors du dossier temporaire prévu. Deux points d'entrée identiques, tous deux atteignables depuis l'interface d'import (Coach → Cours Audio, mode Archive ZIP ; Radio → import de bibliothèque) :

- [`backend/app/utils/audio_importer.py:186`](../backend/app/utils/audio_importer.py) — `import_audio_course_from_zip`
- [`backend/app/utils/radio_importer.py:123`](../backend/app/utils/radio_importer.py) — import de bibliothèque radio

La restauration de sauvegarde (`routers/settings.py`) n'est PAS concernée : elle lit des membres nommément (`zf.read("database.db")`), jamais `extractall()`.

### Décision (aucune ambiguïté produit — fix standard)

Un helper unique `safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None` (nouveau module `backend/app/utils/zip_safety.py`) :
- Pour chaque membre, résout `(dest_dir / member.filename).resolve()` et vérifie qu'il reste `dest_dir` ou un de ses descendants (`os.path.commonpath` ou `Path.is_relative_to`, Python ≥ 3.9 — confirmé disponible, `requirements.txt` cible 3.13).
- Rejette (exception explicite, message clair) au premier membre suspect plutôt que d'extraire partiellement puis échouer — une archive malveillante ne doit laisser AUCUN fichier sur disque.
- Remplace les deux appels `zf.extractall(tmp_dir)` par `safe_extract_zip(zf, tmp_dir)`.

Aucune décision produit à trancher : correctif de sécurité pur, comportement fonctionnel inchangé pour toute archive légitime.

---

## 2. Intégrité des mises à jour desktop

### Constat (révisé après audit)

Contrairement à l'hypothèse initiale, une vérification SHA-256 existe déjà et est solide : [`update_orchestrator.py::download_with_progress`](../backend/app/utils/update_orchestrator.py) télécharge par blocs, calcule le SHA-256 en direct, et le compare au champ `digest` natif renvoyé par l'API GitHub Releases pour chaque asset — supprimant le fichier et levant une erreur explicite en cas de mismatch. Actif sur les 3 profils desktop (Windows/macOS/Linux).

**Le trou réel** : [`routers/updates.py:227`](../backend/app/routers/updates.py) calcule `asset_digest` par `matched.get("digest") if matched else None` — si l'asset attendu n'est pas retrouvé dans la release (nom de fichier différent, release mal formée, bug de correspondance), `asset_digest` vaut `None`. `download_with_progress` traite `expected_digest` absent comme "rien à vérifier" (`if expected_digest:`) et laisse l'installation se poursuivre **sans aucune vérification, silencieusement**.

### Décision validée (2026-09-17)

**Fail-closed** : l'absence d'empreinte devient un cas d'échec explicite, pas un cas ignoré.
- `download_with_progress` (ou son appelant direct dans `run_update_pipeline`) refuse de procéder si `expected_digest` est `None`, avec un message clair ("Empreinte d'intégrité indisponible pour cet asset — installation annulée par précaution.") au lieu de télécharger sans filet.
- Effet de bord accepté et voulu : une release GitHub mal formée (asset renommé, digest absent côté API) bloque désormais la mise à jour automatique plutôt que de l'exécuter à l'aveugle — un rollback/nouvelle release corrige la situation, préférable à une installation non vérifiée avec privilèges élevés.

---

## 3. Télémétrie de flotte — reportée, spec de référence pour une future option opt-in

### Décision validée (2026-09-17)

**Pas d'implémentation maintenant.** Un heartbeat systématique, même minimal, contredit le positionnement produit "local-first, zéro télémétrie" dès l'instant où il est actif par défaut — la valeur opérationnelle (savoir qu'un appareil est silencieux, sans savoir pourquoi) ne compense pas le coût de confiance pour un produit qui vend explicitement l'absence de télémétrie. Retiré du périmètre d'implémentation ; décision et raisonnement documentés dans les directives d'architecture pour qu'une session future ne le réintroduise pas sans un besoin explicite et nouveau.

### Spec de référence si le besoin apparaît un jour

Pour rester cohérent avec le positionnement, toute future version devrait être :
- **Opt-in explicite côté client**, jamais activé par défaut ni à l'insu de l'exploitant de l'appareil — un bouton "Activer le support à distance" dans Réglages, désactivable à tout moment, avec un indicateur visible pendant qu'il est actif (pas un arrière-plan silencieux).
- **Contenu minimal** : identifiant d'appareil, version installée, horodatage — pas de métriques matérielles détaillées par défaut (déjà tranché au 2026-09-17, à réévaluer si la fonctionnalité est un jour implémentée).
- **Infra à décider à ce moment-là** (Cloudflare Worker en réutilisant l'infra déjà en place pour `apt.bobine.fit`, vs service tiers dédié) — non tranché ici puisque non implémenté.

---

## 4. Dependabot

### Décision validée (2026-09-17)

**PR à revue manuelle**, aucun auto-merge. Un fichier `.github/dependabot.yml` couvrant les écosystèmes réellement présents dans le dépôt :

| Écosystème | Répertoire | Fréquence |
|---|---|---|
| `npm` | `/frontend` | hebdomadaire |
| `pip` | `/backend` | hebdomadaire |
| `cargo` | `/assistant` | hebdomadaire |
| `gradle` | `/android` | hebdomadaire |
| `github-actions` | `/` | hebdomadaire |

PR groupées par écosystème (limite le bruit — une PR par écosystème par run plutôt qu'une par dépendance), pas de config `auto-merge`. Revue et merge restent manuels, au rythme du mainteneur.

