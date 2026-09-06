# Cahier des charges & Faisabilité — Portabilité iPadOS (Bobine sur iPad)

> Document prospectif pour l'extension future de Bobine vers l'écosystème Apple iPad (tablettes équipées d'un port USB-C ou Thunderbolt avec sortie vidéo filaire).

---

## 1. Vision & Cas d'Usage (Pupitre Coach & Régie Vidéo Autonome)

Dans la configuration studio classique, Bobine fonctionne sur un mini PC x86-64 (ex. Dell Wyse 5070 ou appliance Debian 13) relié en HDMI à l'écran de cours, et piloté via un smartphone ou un ordinateur portable sur le réseau Wi-Fi.

**La vision iPadOS** :
Permettre à un iPad récent fixé au mur du studio ou posé sur le pupitre coach d'assurer l'intégralité du rôle de régie vidéo autonome, connecté à un simple **dock USB-C / Thunderbolt alimenté avec sortie HDMI / DisplayPort** :
1. **Écran tactile de l'iPad** : Affiche l'interface d'administration, le planning des cours, la console coach et la télécommande tactile.
2. **Écran TV ou Vidéoprojecteur (via le câble vidéo du dock)** : Affiche le flux plein écran `/cinema` ou `/kiosk` en 1080p ou 4K avec décodage matériel via le moteur média d'Apple Silicon (décodeurs HEVC, H.264 et ProRes intégrés).
3. **Moteur local autonome** : L'iPad héberge les bases SQLite et les fichiers médias en stockage local, garantissant une diffusion 100% hors-ligne insensible aux pannes internet.

---

## 2. Modèles iPad Cibles & Prérequis Matériels

Tous les iPads ne supportent pas la sortie vidéo déportée distincte (mode bureau étendu). Le critère matériel déterminant est la présence d'un contrôleur USB-C supportant DisplayPort Alt Mode ou Thunderbolt :

| Gamme iPad | Contrôleur Vidéo | Débit Port | Résolution Vidéo Externe | Statut Compatibilité |
|---|---|---|---|---|
| **iPad Pro 11" & 12.9" / 13" (M1, M2, M4)** | **Thunderbolt / USB 4** | Jusqu'à 40 Gb/s | Jusqu'à 6K @ 60 Hz (Pro Display XDR, écrans 4K/UHD) | **Idéal** — Bande passante maximale, double écran natif |
| **iPad Air (M1, M2 - 11" et 13")** | **USB-C 3.1 Gen 2 / DisplayPort** | 10 Gb/s | Jusqu'à 4K @ 60 Hz | **Recommandé** — Excellent rapport qualité/prix en studio |
| **iPad 10e génération (A14 Bionic)** | USB-C 2.0 / DisplayPort | 480 Mb/s (USB 2.0) | 1080p / 4K @ 30 Hz | **Limité** — Débit USB restreint pour les transferts lourds |
| **iPads Lightning (iPad 9 et antérieurs)** | Lightning vers adaptateur HDMI | Propriétaire | 1080p via flux compressé AirPlay interne | **Incompatible** — Latence et limitation matérielle |

### Accessoires Recommandés
* **Hub ou Dock USB-C / Thunderbolt** : Doté d'une sortie HDMI 2.0 / DisplayPort 1.4, d'un port d'alimentation USB-C Power Delivery (≥ 45W) et de ports USB-A pour brancher une télécommande physique ou un disque de transfert.
* **Support mural sécurisé** : Boîtier antivol VESA avec ventilation passive et passage de câble dissimulé.

---

## 3. Architecture Logicielle & Gestion du Double Affichage

À la différence d'un simple miroir d'écran (qui duplique bêtement l'écran de la tablette sur la TV avec des bandes noires), l'application Bobine iPadOS doit exploiter l'API multi-écrans native d'iOS :

```
┌─────────────────────────────────────────────────────────────┐
│                       Bobine.ipa                            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │     Couche Native iPadOS (SwiftUI / AVFoundation)      │  │
│  │                                                       │  │
│  │   ┌─────────────────────┐   ┌──────────────────────┐  │  │
│  │   │   UIWindowScene     │   │   UIWindowScene      │  │  │
│  │   │   (Écran iPad)      │   │   (Écran Externe)    │  │  │
│  │   │                     │   │                      │  │  │
│  │   │  • Console Coach    │   │  • Lecteur Kiosque   │  │  │
│  │   │  • Planning & Admin │   │  • Flux Vidéo 4K     │  │  │
│  │   │  • Réglages Studio  │   │  • Audio Déporté     │  │  │
│  │   └─────────────────────┘   └──────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Moteur de Stockage & Données             │  │
│  │                                                       │  │
│  │   • SQLite local (database.db)                        │  │
│  │   • Stockage sandboxé (Vidéos, musiques, affiches)   │  │
│  │   • Serveur HTTP local embarqué / WKWebView IPC       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Principes Clés
1. **Écoute de l'événement d'écran externe** : Observation de `UIScreenDidConnectNotification` ou gestion dynamique via `UIWindowSceneSessionRoleExternalDisplayNonInteractive`.
2. **Scène principale (Écran interne iPad)** : Présentation de l'interface d'administration réactive (Next.js statique rendu dans un `WKWebView` optimisé ou interface native SwiftUI).
3. **Scène secondaire (Écran externe HDMI)** : Fenêtre dédiée au lecteur vidéo utilisant `AVPlayerLayer` pour une accélération matérielle maximale et une consommation thermique minimale.

---

## 4. Spécificités & Défis Techniques d'Ingénierie sur iPadOS

La plateforme Apple présente des atouts majeurs (puissance des puces M-series, fiabilité de décodage, écrans de haute qualité) mais impose des contraintes architecturales distinctes d'Android :

### A. Exécution d'Arrière-Plan & Sandbox Système
* **Contrainte** : iOS n'autorise pas l'exécution libre d'un processus daemon en tâche de fond comme un serveur Uvicorn/Python standard.
* **Piste technique** : 
  * Option 1 : Moteur client local-first en TypeScript/Swift où la logique de planification et de base de données est gérée directement côté application sans nécessiter de serveur Python séparé.
  * Option 2 : Embarquement d'un runtime Python portable (PythonKit ou binaire CPython statique lié à l'application) initialisé lors du lancement au premier plan.

### B. Maintien en Éveil 24/7 & Mode Kiosque
* **Anti-mise en veille** : Activation programmatique de `UIApplication.shared.isIdleTimerDisabled = true` pour empêcher l'extinction de l'écran pendant les cours.
* **Verrouillage Kiosque (Accès Guidé)** : Utilisation de la fonction native *Guided Access* d'iOS pour verrouiller l'iPad sur l'application Bobine sans permettre le retour à l'écran d'accueil par geste tactile.
* **Gestion de la Batterie** : Sur iPadOS 17+, activation de la limite de charge à 80% dans les Réglages Batterie pour préserver l'accumulateur lors d'une alimentation permanente sur dock.

---

## 5. Statut & Comparaison avec la Feuille de Route Android

| Critère | Volet Android | Volet iOS / iPadOS |
|---|---|---|
| **Maturité d'ingénierie** | Étude de faisabilité technique avancée (Chaquopy documenté) | Piste prospective explorée, non engagée techniquement |
| **Exécution serveur locale** | Éprouvée via CPython 3.11 sur Android (Chaquopy) | À étudier (contraintes fortes de sandbox Apple) |
| **Sortie vidéo filaire** | DisplayPort Alt Mode (Xiaomi Pad 6/7/8, Galaxy Tab) | Thunderbolt / DisplayPort (iPad Pro M-series, iPad Air M2) |
| **Distribution** | APK installable directement hors store | Distribution Enterprise, Ad-Hoc ou validation App Store |
| **Engagement calendrier** | À l'étude en interne | Piste prospective sans date de livraison |
