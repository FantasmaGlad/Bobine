# Politique de sécurité

Bobine est maintenu par un seul développeur, avec un processus de traitement des vulnérabilités documenté et vérifiable. Cette page explique comment signaler une vulnérabilité, comment chiffrer le rapport, ce que vous pouvez attendre en retour et comment vérifier l'authenticité de ce que nous publions.

Version anglaise : [SECURITY.md](SECURITY.md). Politique lisible par machine ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116), signée OpenPGP) : <https://bobine.fit/.well-known/security.txt>. Page de politique du site : <https://bobine.fit/fr/securite>.

## Versions prises en charge

Les correctifs de sécurité sont publiés dans la dernière version stable et dans le canal Bêta (tag mobile `beta`, reconstruit depuis `main`). Le projet n'a qu'une seule branche de développement : les versions antérieures ne reçoivent pas de correctifs rétroportés. La mise à jour vers la dernière version stable est la remédiation prise en charge.

## Signaler une vulnérabilité

N'ouvrez ni ticket ni discussion publique pour une vulnérabilité. Utilisez l'un de ces canaux privés :

1. **Signalement privé de vulnérabilité GitHub** (à privilégier pour tout détail exploitable) : [onglet Security, « Report a vulnerability »](https://github.com/FantasmaGlad/Bobine/security/advisories/new). Seuls les mainteneurs voient le rapport.
2. **E-mail** : [security@bobine.fit](mailto:security@bobine.fit).

Merci d'indiquer le composant et la version concernés, les étapes de reproduction, l'impact observé et, si possible, une preuve de concept minimale.

### Chiffrer votre rapport

Tout rapport contenant des détails exploitables doit être chiffré avec la clé publique OpenPGP ci-dessous. Si vous ne pouvez pas utiliser PGP, utilisez le signalement privé GitHub, chiffré en transit et visible des seuls mainteneurs, plutôt qu'un e-mail en clair.

| | |
|---|---|
| Identité | Bobine Security `<security@bobine.fit>` |
| Algorithmes | Ed25519 (certifier, signer) et Curve25519 (chiffrer) |
| Empreinte | `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2` |
| Création / expiration | 2026-10-07 / 2028-10-06 |
| Clé privée | protégée par une phrase secrète, détenue par le mainteneur, avec un certificat de révocation |

La clé est publiée par trois canaux indépendants. Récupérez-la depuis au moins deux d'entre eux et vérifiez que l'empreinte correspond avant de l'utiliser :

- ce dépôt : [`docs/security/bobine-security-public-key.asc`](docs/security/bobine-security-public-key.asc)
- le site : <https://bobine.fit/.well-known/security.asc>
- découverte par Web Key Directory OpenPGP : `gpg --locate-keys security@bobine.fit`

```bash
gpg --locate-keys security@bobine.fit
gpg --fingerprint security@bobine.fit
# attendu : 23CA D324 C507 FB0F 97E6  AECA 6E4C 020E F8BD FEB2
```

### Créer votre propre paire de clés

Pour que nous puissions vous répondre chiffré, créez votre propre paire de clés et joignez votre clé publique à votre message (ou indiquez où la récupérer). Ne partagez jamais votre clé privée.

```bash
gpg --quick-generate-key "Votre Nom <vous@exemple.org>" future-default default 2y
gpg --armor --export vous@exemple.org > ma-cle-publique.asc
```

## Ce que vous pouvez attendre

| Étape | Objectif |
|---|---|
| Accusé de réception de votre rapport | sous 7 jours |
| Analyse et évaluation de la gravité | communiquées après l'accusé de réception |
| Correctif publié | dès que possible, annoncé dans les notes de version |
| Divulgation coordonnée | 90 jours par défaut, prolongeable d'un commun accord, raccourcie si la faille est déjà exploitée |

Ce sont des objectifs et non des engagements contractuels : le projet n'a qu'un mainteneur. Lorsque l'impact le justifie, un identifiant CVE est demandé via GitHub Security Advisories, et les personnes qui le souhaitent sont créditées.

## Périmètre

Dans le périmètre : le logiciel Bobine et ses installateurs (`install.sh`, `install-tor.sh`, paquets Windows, macOS, Linux et Android), le site `bobine.fit` et ses routes serveur, le dépôt APT `apt.bobine.fit` et sa chaîne de signature, ainsi que les miroirs Tor du site et du dépôt.

Hors périmètre : les failles des services tiers (Vercel, Cloudflare, GitHub, Amazon, AliExpress, Hugging Face, OpenRouter, Resend), l'ingénierie sociale et le hameçonnage, l'accès physique, les attaques par déni de service, les tests de charge et les scans automatisés massifs, les constats sans impact démontrable, et les erreurs de contenu ou de traduction.

## Recherche de bonne foi

Une recherche menée de bonne foi dans le périmètre ci-dessus ne fera l'objet d'aucune action de notre part. En contrepartie : n'accédez pas aux données d'autres personnes au-delà du strict nécessaire pour démontrer la faille, ne modifiez et ne détruisez aucune donnée, ne perturbez pas le service, n'installez aucune persistance et ne divulguez rien avant la correction. Il n'existe pas de programme de récompense financière.

## Vérifier ce que nous publions

Le dépôt APT est signé par une clé de signature dédiée, distincte de la clé de réception ci-dessus et jamais utilisée pour recevoir des rapports.

```bash
curl -fsSL https://apt.bobine.fit/bobine.gpg | gpg --show-keys --fingerprint
# clé principale : B77D 96D7 2F84 F36A CAA3  F872 9CBF 497D 829E E15A
# sous-clé de signature : 941B 6F52 6A72 59F4 694C  F4BC 1B5D 18A9 76FA AD15
```

Le script `install-tor.sh` épingle l'empreinte de la clé principale et s'arrête si elle diffère. Les mises à jour automatiques vérifient le condensé SHA-256 des fichiers publiés sur GitHub Releases.

## Historique du document

| Date | Modification |
|---|---|
| 2026-10-07 | Publication de la politique avec une première clé de réception (`8208 FFD3 F7AB 4DD3 6B0A CDD8 4726 A378 F683 265A`). |
| 2026-10-07 | Première clé révoquée et retirée le jour même, quelques heures après sa publication, car sa phrase secrète était inutilisable. Aucun rapport n'avait été reçu et la clé privée n'a jamais été exposée. La clé publique révoquée, avec sa signature de révocation, est publiée dans [`docs/security/revoked/`](docs/security/revoked/bobine-security-8208FFD3F7AB4DD3-REVOKED.asc). |
| 2026-10-07 | Création et publication de la clé de réception actuelle `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2`. Signature de `security.txt` avec cette clé. |

Cet historique recense tout changement de clé, d'empreinte ou d'engagement. Une rotation ou une révocation de clé y est annoncée, ainsi que sur <https://bobine.fit/fr/securite>.
