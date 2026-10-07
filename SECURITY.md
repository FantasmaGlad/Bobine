# Security Policy

Bobine is maintained by a single developer, with a documented and verifiable vulnerability-handling process. This page explains how to report a vulnerability, how to encrypt the report, what to expect in return, and how to verify the authenticity of what we publish.

French version: [SECURITY.fr.md](SECURITY.fr.md). Machine-readable policy ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116), OpenPGP-signed): <https://bobine.fit/.well-known/security.txt>. Website policy page: <https://bobine.fit/en/securite>.

## Supported versions

Security fixes are released in the latest stable version and in the Beta channel (mobile tag `beta`, rebuilt from `main`). The project has a single development branch: earlier releases do not receive backported fixes. Updating to the latest stable release is the supported remediation.

## Reporting a vulnerability

Do not open a public issue or discussion for a vulnerability. Use one of these private channels:

1. **GitHub private vulnerability reporting** (preferred for anything exploitable): [Security tab, "Report a vulnerability"](https://github.com/FantasmaGlad/Bobine/security/advisories/new). Only the maintainers can see the report.
2. **E-mail**: [security@bobine.fit](mailto:security@bobine.fit).

Please include the affected component and version, the steps to reproduce, the impact you observe and, if possible, a minimal proof of concept.

### Encrypt your report

Any report containing exploitable details must be encrypted with the OpenPGP public key below. If you cannot use PGP, use the private GitHub report, which is encrypted in transit and visible only to the maintainers, rather than plain e-mail.

| | |
|---|---|
| Identity | Bobine Security `<security@bobine.fit>` |
| Algorithms | Ed25519 (certify, sign) and Curve25519 (encrypt) |
| Fingerprint | `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2` |
| Created / expires | 2026-10-07 / 2028-10-06 |
| Private key | protected by a passphrase, held by the maintainer, with a revocation certificate |

The key is published through three independent channels. Retrieve it from at least two of them and check that the fingerprint matches before use:

- this repository: [`docs/security/bobine-security-public-key.asc`](docs/security/bobine-security-public-key.asc)
- the website: <https://bobine.fit/.well-known/security.asc>
- OpenPGP Web Key Directory discovery: `gpg --locate-keys security@bobine.fit`

```bash
gpg --locate-keys security@bobine.fit
gpg --fingerprint security@bobine.fit
# expected: 23CA D324 C507 FB0F 97E6  AECA 6E4C 020E F8BD FEB2
```

### Create your own key pair

So that we can reply to you encrypted, create your own key pair and attach your public key to your message (or tell us where to fetch it). Never share your private key.

```bash
gpg --quick-generate-key "Your Name <you@example.org>" future-default default 2y
gpg --armor --export you@example.org > my-public-key.asc
```

## What to expect

| Step | Target |
|---|---|
| Acknowledgment of your report | within 7 days |
| Triage and severity assessment | communicated after acknowledgment |
| Fix released | as soon as practicable, announced in the release notes |
| Coordinated disclosure | 90 days by default, extendable by mutual agreement, shortened if the flaw is already exploited |

These are objectives, not contractual commitments: the project has a single maintainer. When the impact justifies it, a CVE identifier is requested through GitHub Security Advisories, and reporters who wish it are credited.

## Scope

In scope: the Bobine software and its installers (`install.sh`, `install-tor.sh`, Windows, macOS, Linux and Android packages), the website `bobine.fit` and its server routes, the APT repository `apt.bobine.fit` and its signing chain, and the Tor mirrors of the site and of the repository.

Out of scope: flaws in third-party services (Vercel, Cloudflare, GitHub, Amazon, AliExpress, Hugging Face, OpenRouter, Resend), social engineering and phishing, physical access, denial-of-service attacks, load tests and mass automated scans, findings without demonstrable impact, and content or translation errors.

## Good-faith research

Research carried out in good faith within the scope above will not lead to any action from us. In return: do not access other people's data beyond what is strictly needed to demonstrate the flaw, do not modify or destroy data, do not disrupt the service, do not install persistence, and do not disclose anything before the fix. There is no financial reward program.

## Verifying what we publish

The APT repository is signed with a dedicated signing key, distinct from the report key above and never used to receive reports.

```bash
curl -fsSL https://apt.bobine.fit/bobine.gpg | gpg --show-keys --fingerprint
# primary key: B77D 96D7 2F84 F36A CAA3  F872 9CBF 497D 829E E15A
# signing subkey: 941B 6F52 6A72 59F4 694C  F4BC 1B5D 18A9 76FA AD15
```

The `install-tor.sh` script pins the primary key fingerprint and stops if it differs. Automatic updates verify the SHA-256 digest of the files published on GitHub Releases.

## Document history

| Date | Change |
|---|---|
| 2026-10-07 | Policy published. Report key `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2` created. `security.txt` signed with this key. |

This history lists every change of key, fingerprint or commitment. A key rotation or revocation is announced here and on <https://bobine.fit/en/securite>.
