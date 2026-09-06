; Installeur Windows de Bobine (PortabiliteCrossPlatformX, Lot 1).
;
; NON TESTÉ — écrit d'après la documentation Inno Setup (jrsoftware.org/ishelp),
; à valider sur une vraie machine Windows avant toute distribution. Compile
; avec ISCC.exe (Inno Setup 6+), après avoir construit
; packaging/windows/bobine.spec avec PyInstaller SUR WINDOWS (pas de
; cross-compilation possible) :
;
;   cd backend && pyinstaller ../packaging/windows/bobine.spec
;   iscc packaging\windows\bobine.iss
;
; Source de vérité de la disposition attendue : dist/Bobine/ (généré par
; PyInstaller, cf. bobine.spec) doit contenir BobineBackend.exe,
; BobineTray.exe, config.toml, logo_bobine_icon.png et frontend/out/ à plat
; (pas de sous-dossier _internal — cf. contents_directory="." dans le spec).

#define MyAppName "Bobine"
#define MyAppVersion "2.0.1"
#define MyAppPublisher "Bobine"
#define MyAppURL "https://bobine.fit"
#define MyDistDir "..\..\backend\dist\Bobine"

[Setup]
AppId={{B0B1AE00-C1AE-4A00-9A11-B0B1AE000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; %ProgramFiles% : décision #CDC§5.2 — les données applicatives vivent sous
; %ProgramData%\Bobine (résolu dynamiquement par backend/app/config.py),
; PAS ici (dossier non inscriptible par un utilisateur standard).
DefaultDirName={autopf}\Bobine
DefaultGroupName=Bobine
; Décision #7 du CDC : pas de signature de code pour l'instant — Windows
; affichera l'avertissement SmartScreen "Éditeur non reconnu" à
; l'installation (limitation connue et assumée, cf. README).
; Élévation nécessaire pour écrire dans %ProgramFiles% et créer
; %ProgramData%\Bobine (première installation) ; les lancements
; ultérieurs de BobineTray, eux, tournent en utilisateur standard.
PrivilegesRequired=admin
OutputDir=..\..\dist-installer
OutputBaseFilename=Bobine-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
; Licence AGPL-3.0 du dépôt, affichée avant installation (cf. plan
; d'implémentation §2 — "décision explicite sur la licence").
LicenseFile=..\..\LICENSE
SetupIconFile=bobine.ico
UninstallDisplayIcon={app}\BobineBackend.exe

; Section [Languages] : l'app démarre en français par défaut
; (DEFAULT_LANGUAGE = "fr", AppSettingsContext.tsx) sans détection de
; langue navigateur/OS — un installeur anglais par défaut (comportement
; Inno Setup sans cette section) serait incohérent avec l'application
; elle-même (cf. plan §2).
[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Tout le dossier de sortie PyInstaller, à plat (cf. bobine.spec,
; contents_directory=".") : les deux exécutables, config.toml,
; logo_bobine_icon.png, frontend/out/ et les dépendances Python figées.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Bobine"; Filename: "{app}\BobineTray.exe"
Name: "{group}\{cm:UninstallProgram,Bobine}"; Filename: "{uninstallexe}"
; Lancement automatique de BobineTray à l'ouverture de session utilisateur
; (par utilisateur, pas system-wide — cf. CDC §5.3, pas de Service Windows
; pour ce profil).
Name: "{userstartup}\Bobine"; Filename: "{app}\BobineTray.exe"

[Run]
; Règle de pare-feu pour le port d'écoute backend (0.0.0.0:8000, requis
; par la télécommande mobile depuis n'importe quel appareil du LAN — cf.
; plan §2, "sans cette règle, la télécommande mobile peut simplement ne
; pas fonctionner"). `netsh` est natif Windows, aucune dépendance externe.
; Échec toléré (`flags: runhidden skipifsilent"; ...`) : mieux vaut une
; installation qui continue sans la règle qu'un installeur qui échoue
; entièrement sur cette seule étape.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Bobine"" dir=in action=allow program=""{app}\BobineBackend.exe"" enable=yes profile=any"; Flags: runhidden; StatusMsg: "Configuration du pare-feu…"
; Lance BobineTray (qui démarre lui-même BobineBackend, cf. CDC §5.3)
; immédiatement après l'installation, sans attendre la prochaine session.
Filename: "{app}\BobineTray.exe"; Description: "Lancer Bobine"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Symétrique de la règle [Run] ci-dessus, retirée à la désinstallation.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Bobine"""; Flags: runhidden

; Note (décision #6 du CDC — aucune contrainte de migration) : cet
; installeur ne propose PAS de conserver/purger %ProgramData%\Bobine à la
; désinstallation — Inno Setup ne touche par défaut qu'à {app}
; (%ProgramFiles%\Bobine). Un utilisateur qui réinstalle retrouve donc ses
; données ; un utilisateur qui veut un nettoyage complet doit supprimer
; %ProgramData%\Bobine manuellement (à documenter dans le README, cf.
; plan §2 section "Documentation").
