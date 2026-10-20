# Corpus et oracle audio

Ce banc fige le comportement des utilitaires Python actuels avant tout
remplacement de l’extraction audio. Il ne modifie aucun média utilisateur,
n’ouvre aucune base de données et ne fait pas partie du paquet distribué.

Le générateur utilise uniquement Python standard et `ffmpeg`. L’oracle utilise
l’environnement Python du backend existant, dont Pillow, ainsi que `ffprobe`
et `ffmpeg`. Aucun téléchargement de média ou paquet supplémentaire n’est requis.

## Exécution

Depuis la racine du dépôt, choisir un nouveau dossier hors du dépôt :

```bash
backend/.venv/bin/python scripts/media-bench/generate.py /var/tmp/bobine-audio-corpus
backend/.venv/bin/python scripts/media-bench/baseline.py \
  /var/tmp/bobine-audio-corpus \
  /var/tmp/bobine-audio-corpus/python-baseline.json --repeats 3
backend/.venv/bin/python -m pytest backend/tests/test_audio_metadata_contract.py -q
```

Sous Windows, utiliser un dossier temporaire hors du dépôt et le Python du
backend correspondant. `--ffmpeg` permet de choisir le binaire du générateur.
L’oracle suit les résolveurs du backend ; `BOBINE_FFMPEG_BIN` et
`BOBINE_FFPROBE_BIN` permettent de choisir explicitement les binaires analysés.

Le dossier de corpus et le fichier de référence doivent être nouveaux : aucun
écrasement automatique. Les données temporaires de l’oracle sont isolées avant
les imports. Seuls les modules utilitaires sont importés ; l’oracle vérifie que
le module de base de données n’a pas été chargé. Les rapports emploient des
identifiants et chemins relatifs. Conserver les médias et rapports générés hors
du dépôt, avec le manifeste auquel leurs empreintes se rapportent.

## Couverture

Avec tous les encodeurs disponibles, le générateur produit **55 fichiers audio** :

- MP3 CBR/VBR avec et sans en-tête Xing/Info ; FLAC, WAV, AAC brut, AAC/M4A,
  Vorbis/Ogg, Opus/Ogg, WMA et AIFF : quatre variantes par famille, soit 48 fichiers.
- Quatre pochettes embarquées : JPEG opaque et PNG transparent dans MP3 et FLAC.
- Trois corruptions : vide, octets arbitraires, en-tête ID3 tronqué.

Les variantes couvrent les tags absents, Unicode, champs vides, espaces, piste
et disque sous forme `03/12`, date complète, année dans du texte et noms avec
espaces, Unicode, apostrophe, crochets et tiret initial. Le son est une sinusoïde
synthétique de 1,37 seconde ; les images sont générées localement. Aucun contenu
tiers n’est inclus.

Chaque échec d’encodage est affiché et enregistré dans `manifest.json` : il ne
devient jamais un fichier prétendument validé. Un corpus de moins de 40 fichiers
échoue. Consulter aussi `failures` lorsque ce seuil est atteint : le nombre total
ne garantit pas à lui seul la disponibilité de toutes les familles optionnelles.
Un échec initial de génération d’image interrompt immédiatement la commande.

**Limites explicites :** pas de fixture VBRI (libmp3lame génère Xing/Info), de
chemin contenant des octets non UTF-8, de fichier dépassant les limites mémoire,
de MP3 avec plusieurs pochettes ou de permission inaccessible. Ces cas devront
être ajoutés avant d’affirmer leur prise en charge. Le comportement de collision
de casse des tags est couvert par les tests simulant ffprobe ; un conteneur peut
fusionner ces tags lors de son écriture et ne convient pas à ce test.

## Format du manifeste et de la référence

`manifest.json` contient `schema_version: 1`, la version ffmpeg, les limites,
les échecs et une liste `entries`. Une entrée comprend :

| Champ | Sens |
|---|---|
| `id` | Identifiant stable du cas |
| `type` | Famille de format ou `corrupt` |
| `path` | Chemin relatif au corpus |
| `sha256` | Empreinte attendue du fichier généré |
| `expected` | Intention de génération : durée source, tags demandés, pochette ou corruption |

L’intention n’est pas une assertion sur la durée du conteneur ou les tags
conservés : les encodeurs ajoutent du délai et certains formats perdent des
tags. L’oracle capture le résultat réellement obtenu avec les utilitaires
Python, sans le normaliser. Les octets encodés peuvent varier avec la version
ffmpeg ; les empreintes lient chaque référence à son corpus précis.

`python-baseline.json` lie le manifeste par SHA-256 et indique les versions
Python/ffmpeg/ffprobe. Pour chaque identifiant :

- `profiles.radio.value` contient tous les champs de `extract_radio_metadata` ;
  `profiles.course.value` contient la durée de `extract_audio_duration`.
- `presence` distingue valeur nulle et valeur présente ; les temps par fonction
  comprennent les échantillons et leur médiane. Des résultats différents entre
  répétitions font échouer le banc.
- `cover` décrit la présence, le format, le mode, la taille et le SHA-256 du
  JPEG final produit par ffmpeg puis Pillow ; les images temporaires sont nettoyées.
- `ffprobe` conserve le code de sortie et le JSON brut lorsque l’analyse réussit,
  avec `filename` remplacé par le chemin relatif. Aucun stderr contenant des
  chemins locaux n’est copié dans la référence.

Le profil radio conserve uniquement la durée du conteneur. Le profil cours
essaie ensuite le premier flux doté d’une durée, même si ce flux n’est pas
audio ; une durée présente mais invalide ne déclenche pas le repli. Les tags
du premier flux audio sont ajoutés avec `setdefault` avant passage en minuscules :
`TITLE` et `title` peuvent donc produire un résultat surprenant. Les tests de
contrat préservent précisément ces comportements historiques et les priorités
d’alias, numéros, années et titres de repli.

Les mesures sont celles des fonctions d’extraction sur l’hôte de développement.
Elles excluent les écritures SQL, les copies et transcodages de l’import complet.
L’état du cache disque n’est pas contrôlé. Une référence locale ne valide aucun
autre système ou appareil. Les SHA de pochettes servent à reproduire cet oracle ;
une extraction d’octets bruts ne doit pas leur être comparée comme si elle avait
déjà subi les deux encodages JPEG et le redimensionnement actuels.

## Comparer le composant expérimental

Après construction du binaire, le comparateur utilise le **vrai `MediaClient`**
Python avec activation explicite limitée à cette instance :

```bash
backend/.venv/bin/python scripts/media-bench/compare.py \
  /var/tmp/bobine-audio-corpus \
  /var/tmp/bobine-audio-corpus/python-baseline.json \
  --binary media/target/release/bobine-media \
  --output /var/tmp/bobine-audio-corpus/native-comparison.json --repeats 3
```

Le comparateur vérifie l’association manifeste/référence et les empreintes des
médias, puis exécute les deux profils et l’inspection de pochette. Le titre natif
nul reçoit le repli sur le nom du fichier utilisé en radio. Les neuf champs radio
sont comparés, avec une tolérance maximale de 50 ms uniquement pour la durée ;
le profil cours compare seulement la durée. Les répétitions doivent rendre les
mêmes valeurs et motifs de repli.

La sortie JSON sépare `native`, `fallback:unsupported`, `fallback:corrupt` et les
autres raisons. Un repli attendu ne compte jamais comme une analyse native
réussie. Les erreurs du transport, du protocole ou de disponibilité échouent ;
une divergence sur une valeur native acceptée échoue également avec un code de
sortie non nul. Le banc capture le motif du repli : il n’exécute pas à nouveau
le traitement Python et ne mesure pas le coût de ce repli.

Seule l’absence de pochette prouvée par le composant est validée. Une pochette
présente peut légitimement demander le chemin Python avec `ambiguous_cover` ;
des octets d’image natifs demanderaient une validation de normalisation
complémentaire et font échouer ce banc tant qu’elle n’existe pas.

Le rapport conserve les empreintes des médias, du binaire, des utilitaires,
du manifeste et de la référence avant/après. Une mutation échoue. Les temps
incluent le client réel ; la première requête comprend le démarrage et
l’identification du processus. Ce sont des mesures locales, sans contrôle du
cache ni import complet. Une comparaison sans divergence sur une partie du
corpus ne certifie pas les formats dont l’analyse déclenche un repli.
