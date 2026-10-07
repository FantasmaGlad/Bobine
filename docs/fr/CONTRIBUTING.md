# Contribuer à Bobine

Merci d'envisager une contribution. Bobine fonctionne sans surveillance dans des salles de sport et des studios, sur du matériel que son mainteneur ne peut pas toujours atteindre : une régression n'est pas un désagrément, c'est un cours qui ne démarre pas. Les exigences ci-dessous en découlent. Elles sont strictes parce que le logiciel est utilisé en production, pas pour vous décourager.

Version anglaise : [CONTRIBUTING.md](../../CONTRIBUTING.md). En participant, vous acceptez de respecter le [Code de conduite](CODE_OF_CONDUCT.md). Les vulnérabilités ne se signalent ni par ticket ni par demande de fusion : voir [SECURITY.md](SECURITY.md).

## Avant de commencer

- Recherchez d'abord dans les tickets et demandes de fusion existants.
- Pour tout ce qui dépasse une correction simple et évidente (nouvelle fonctionnalité, changement de comportement, refactorisation, nouvelle dépendance), ouvrez un ticket et convenez de l'approche avant d'écrire du code. Une grosse demande de fusion non sollicitée a de fortes chances d'être déclinée, quelle que soit sa qualité.
- Une demande de fusion, un changement logique. Une correction de bug n'embarque pas de refactorisation, et une refactorisation n'embarque pas de fonctionnalité.
- Les tickets et demandes de fusion peuvent être rédigés en français ou en anglais.

## Principes

**Des preuves, pas des suppositions.** Un problème est compris quand vous savez le reproduire et en désigner la cause. Une correction est juste quand vous pouvez montrer qu'elle supprime cette cause. Appuyez vos affirmations sur des faits : journaux, messages d'erreur, versions, étapes exactes de reproduction, mesures. « Ça devrait marcher » et « ça corrige probablement le problème » n'ont pas leur place dans une demande de fusion.

**La cause racine, pas le symptôme.** Ne masquez pas une erreur par un `try`/`except` silencieux, une nouvelle tentative, une temporisation ou un cas particulier qui cache la vraie défaillance. Si la conception sous-jacente est en cause, dites-le et proposez de la corriger à la source.

**Dites ce que vous n'avez pas vérifié.** Indiquez précisément ce que vous avez testé, sur quel système et quelle version, et ce que vous n'avez pas pu tester. Une lacune assumée est bienvenue ; une affirmation non vérifiée présentée comme un fait ne l'est pas.

**Respectez l'architecture.** Lisez [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) avant de toucher au backend, au modèle de données ou au contrat réseau. Bobine fonctionne en un seul processus (FastAPI et SQLite) et entièrement hors ligne. Un changement qui ajoute un service externe, une dépendance au cloud ou un nouveau composant d'arrière-plan exige un accord préalable dans un ticket.

**Exactitude de la documentation.** Ne documentez jamais une fonctionnalité qui n'existe pas ou n'est pas publiée. La documentation utilisateur vit dans `README.md` et `README.fr.md` ; gardez les deux cohérents, et signalez-nous si vous ne pouvez pas fournir la traduction.

## Vous êtes responsable de votre code

Quels que soient les outils que vous utilisez pour écrire du code, vous êtes l'auteur de ce que vous soumettez et vous en répondez.

- Vous devez pouvoir expliquer chaque ligne de votre changement et la raison de sa présence, seul, pendant la revue.
- Vous devez l'avoir exécuté. Une demande de fusion décrivant des tests qui n'ont pas été lancés, ou citant des fonctions, options ou fichiers qui n'existent pas, sera fermée.
- Vous devez avoir le droit de le placer sous licence. Ne soumettez pas de code copié depuis une source dont la licence est incompatible avec l'AGPL-3.0, et vérifiez la provenance de tout bloc important que vous n'avez pas écrit vous-même, y compris la sortie d'un générateur de code.
- Vous devez respecter les conventions et le style du projet, et retirer ce qui n'apporte rien : commentaires passe-partout, code paraphrasé, reformatage sans rapport, abstractions spéculatives, descriptions délayées.
- Une demande de fusion qui ne montre aucune trace de relecture humaine (changements sans rapport, références inventées, prose générique, code qui ne s'intègre pas à la base) est fermée sans retour détaillé.
- Les envois automatisés ou en masse (scripts ouvrant des demandes de fusion, reformatage massif, changements massifs de dépendances) ne sont pas acceptés sans accord préalable. Les mises à jour de dépendances sont traitées par le mainteneur.

Les mainteneurs relisent les contributions sur leur temps. Rendre la revue courte relève de votre responsabilité.

## Environnement de développement

Bobine comporte trois composants. Avant d'ouvrir une demande de fusion, lancez localement les vérifications ci-dessous pour chaque composant que vous avez touché. La CI exécute les mêmes.

| Composant | Dossier | Vérifications |
|---|---|---|
| Backend (Python, FastAPI, SQLite) | `backend/` | `python -m compileall -q backend/app scripts` puis `python -m unittest discover -s backend/tests` (nécessite `ffmpeg` ; la CI utilise Python 3.12) |
| Frontend (Next.js, Node 22) | `frontend/` | `npm ci` puis `npm run build` (CI). `npm run lint` n'est pas imposé par la CI et signale des problèmes existants : n'en introduisez pas de nouveaux dans le code que vous touchez |
| Assistant (Rust, Tauri) | `assistant/` | `cargo clippy --workspace --all-targets -- -D warnings` puis `cargo test --workspace` |

Le schéma de données est géré par SQLAlchemy : les tables sont créées au démarrage, et les colonnes ajoutées aux tables existantes passent par les micro-migrations idempotentes du module de base de données (voir le document d'architecture). Un changement de schéma doit fonctionner sur une base existante sans perte de données et être couvert par un test. Une demande de fusion qui fait échouer un job de CI n'est pas relue tant qu'elle n'est pas verte.

## Plateformes

Bobine cible cinq profils d'exécution : Android (ARM64), Linux bureau, appliance Debian headless, Windows et macOS. Un changement qui touche au comportement système (détection matérielle, alimentation et veille, fenêtrage, sortie audio et vidéo, stockage, processus, réseau, empaquetage) doit être raisonné pour chaque profil, et votre demande de fusion doit indiquer ceux que vous avez testés et ceux que vous n'avez pas testés. Si vous ne pouvez tester que sur un système, dites-le : le mainteneur couvrira les autres.

## Tests

- Une correction de bug inclut un test de non-régression chaque fois que le bug peut être reproduit dans un test automatisé, et ce test doit échouer sans votre correction.
- Un nouveau comportement inclut des tests de son chemin nominal et de ses cas d'échec.
- Quand le test automatisé n'est pas praticable (matériel, affichage, empaquetage), décrivez la procédure manuelle suivie et son résultat.

## Commits

Bobine utilise les [Conventional Commits](https://www.conventionalcommits.org/), en minuscules, avec un scope :

```
type(scope): description courte à l'impératif
```

| Type | Usage |
|---|---|
| `feat` | une fonctionnalité visible par l'utilisateur |
| `fix` | une correction de bug |
| `refactor` | un changement sans effet sur le comportement |
| `perf` | une amélioration de performance mesurée |
| `test` | des tests uniquement |
| `docs` | de la documentation uniquement |
| `build`, `ci`, `chore` | empaquetage, pipelines, maintenance |
| `revert` | l'annulation d'un commit précédent |

Le scope désigne le domaine (`coach`, `playlists`, `audio`, `schedule`, `updates`, `packaging`, `assistant`, `android`, `windows`, `security`, `ci`...). Exemples tirés de l'historique :

```
fix(android): synchroniser wired_display_mode sur la detection HDMI reelle
fix(security): zip-slip audio/radio, fail-closed maj desktop, dependabot
feat(updates): unification et fiabilisation de la mise a jour automatique multi-os
```

- Le sujet est court, précis et dit ce qui change, pas ce que vous en pensez. Les messages peuvent être en français ou en anglais, de façon cohérente au sein d'une demande de fusion.
- Pour tout changement non trivial, ajoutez un corps sous forme de liste à puces : la cause racine résolue, le mécanisme introduit et la façon dont il a été testé.
- Un changement logique par commit ; chaque commit doit compiler et passer les tests seul. Ne laissez pas de commits « fixup », « wip » ou « corrections de revue » dans l'historique final.
- Maintenez votre branche à jour en la rebasant sur `main` plutôt qu'en fusionnant `main` dedans.
- Ne commitez jamais de secrets, d'identifiants, de données personnelles, de fichiers média, de noms d'hôte ou d'adresses IP réels, ni d'artefacts générés. Vérifiez votre diff, vos captures d'écran et vos journaux avant de pousser.

## Demandes de fusion

Ouvrez la demande de fusion vers `main`. La description doit contenir :

1. **Quoi et pourquoi** : le problème, avec le numéro de ticket s'il y en a un.
2. **Comment** : l'approche, et les alternatives écartées le cas échéant.
3. **Vérification** : les commandes exactes lancées et leur résultat, les étapes manuelles et les plateformes couvertes (voir plus haut).
4. **Risques** : ce qui pourrait régresser et comment on s'en apercevrait.
5. **Documentation** : ce que vous avez mis à jour, ou pourquoi rien n'avait à l'être.

Ne modifiez pas `VERSION` ni les fichiers de `docs/releases/` : les versions sont préparées par le mainteneur. Répondez aux commentaires de revue dans leur fil, et poussez les changements sous forme de nouveaux commits jusqu'à la fin de la revue, puis nettoyez l'historique comme convenu.

Une demande de fusion est acceptée lorsque la CI est verte, la revue terminée et le changement conforme à la direction du projet. Une décision de ne pas fusionner concerne le changement, pas la personne ; la raison est donnée.

## Dépendances

Ajouter une dépendance exige une justification dans la demande de fusion : ce qu'elle fait, pourquoi la bibliothèque standard ou une dépendance existante ne suffit pas, sa licence (compatible avec l'AGPL-3.0), son état de maintenance et son empreinte sur une petite appliance. L'exécution doit rester possible sans accès à Internet.

## Licence

Bobine est publié sous [GNU AGPL-3.0](../../LICENSE). En soumettant une contribution, vous déclarez en avoir le droit et acceptez qu'elle soit distribuée sous la même licence.

## Historique du document

| Date | Modification |
|---|---|
| 2026-10-08 | Adoption du guide de contribution. |
