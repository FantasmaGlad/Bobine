; Installeur Windows de Bobine.
;
; Construit et publié par la CI (jobs windows-build et windows-build-arm64) avec
; chaque release ; écrit d'après la documentation Inno Setup
; (jrsoftware.org/ishelp). Compile
; avec ISCC.exe (Inno Setup 6+), après avoir construit
; packaging/windows/bobine.spec avec PyInstaller SUR WINDOWS (pas de
; cross-compilation possible) :
;
;   cd backend && pyinstaller ../packaging/windows/bobine.spec
;   iscc packaging\windows\bobine.iss
;
; Source de vérité de la disposition attendue : dist/Bobine/ (généré par
; PyInstaller, cf. bobine.spec) doit contenir BobineBackend.exe,
; BobineTray.exe, config.toml, logo_bobine_icon*.png, bobine.ico et frontend/out/ à plat
; (pas de sous-dossier _internal — cf. contents_directory="." dans le spec).

#define MyAppName "Bobine"
; Source de vérité unique : le fichier
; VERSION à la racine du dépôt. La CI passe la version exacte via
; `ISCC /DMyAppVersion=...` ; ce garde `#ifndef` la laisse gagner sur le
; repli codé en dur ci-dessous, utilisé uniquement lors d'une compilation
; manuelle sans ce define.
#ifndef MyAppVersion
  #define MyAppVersion "5.0.6"
#endif
; Version utilisée dans le NOM DU FICHIER de l'installeur — délibérément
; distincte de MyAppVersion : par défaut
; identique (paquets stables), mais la CI passe la valeur fixe "beta" ou
; "canary" selon le canal rolling concerné — un seul nom de fichier stable
; dans le temps par canal plutôt qu'un nouveau nom à chaque reconstruction,
; pendant que MyAppVersion (affiché dans "Applications et fonctionnalités"
; Windows) reste la version réelle et précise.
#ifndef MyOutputVersion
  #define MyOutputVersion MyAppVersion
#endif
#ifndef MyOutputSuffix
  #define MyOutputSuffix ""
#endif
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
; %ProgramFiles% : les données applicatives vivent sous
; %ProgramData%\Bobine (résolu dynamiquement par backend/app/config.py),
; PAS ici (dossier non inscriptible par un utilisateur standard).
DefaultDirName={autopf}\Bobine
DefaultGroupName=Bobine
; Pas de signature de code pour l'instant — Windows
; affichera l'avertissement SmartScreen "Éditeur non reconnu" à
; l'installation (limitation connue et assumée, cf. README).
; Élévation nécessaire pour écrire dans %ProgramFiles% et créer
; %ProgramData%\Bobine (première installation) ; les lancements
; ultérieurs de BobineTray, eux, tournent en utilisateur standard.
PrivilegesRequired=admin
OutputDir=..\..\dist-installer
OutputBaseFilename=Bobine-Setup-{#MyOutputVersion}{#MyOutputSuffix}
Compression=lzma2
SolidCompression=yes
; Licence AGPL-3.0 du dépôt, affichée avant installation.
LicenseFile=..\..\LICENSE
; Icône de l'installeur : celle du canal du build, que bobine.spec a choisie d'après le suffixe
; de VERSION et copiée sous le nom fixe bobine.ico dans le dossier PyInstaller (une seule
; décision, prise par le .spec ; ISPP n'a donc aucune règle de canal à dupliquer).
SetupIconFile={#MyDistDir}\bobine.ico
UninstallDisplayIcon={app}\BobineTray.exe
CloseApplications=yes
CloseApplicationsFilter=*Bobine*.exe
RestartApplications=no

; Section [Languages] : l'app démarre en français par défaut
; (DEFAULT_LANGUAGE = "fr", AppSettingsContext.tsx) sans détection de
; langue navigateur/OS — un installeur anglais par défaut (comportement
; Inno Setup sans cette section) serait incohérent avec l'application
; elle-même.
[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Purge des modules C compiles et DLLs existants avant extraction
; pour eviter tout conflit binaire avec des reliquats d'une ancienne installation
Type: files; Name: "{app}\*.pyd"
Type: files; Name: "{app}\*.dll"

[Files]
; Tout le dossier de sortie PyInstaller, à plat (cf. bobine.spec,
; contents_directory=".") : les deux exécutables, config.toml,
; logo_bobine_icon*.png (une par canal), frontend/out/ et les dépendances Python figées.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\BobineTray.exe"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\BobineTray.exe"; Tasks: desktopicon
; Lancement automatique de BobineTray à l'ouverture de session utilisateur
; (par utilisateur, pas system-wide — pas de Service Windows
; pour ce profil).
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\BobineTray.exe"; Parameters: "--startup"

[Run]
; Règle de pare-feu pour le port d'écoute backend (0.0.0.0, 8000 par défaut,
; requis par la télécommande mobile depuis n'importe quel appareil du LAN :
; sans cette règle, la télécommande mobile peut simplement ne pas
; fonctionner). La règle est liée au PROGRAMME (BobineBackend.exe), pas à un
; numéro de port : elle couvre aussi le port de repli que le backend prend si
; le port configuré est occupé (cf. backend/app/utils/port.py). `netsh` est natif Windows, aucune dépendance externe.
; Échec toléré (`flags: runhidden skipifsilent"; ...`) : mieux vaut une
; installation qui continue sans la règle qu'un installeur qui échoue
; entièrement sur cette seule étape.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Bobine"" dir=in action=allow program=""{app}\BobineBackend.exe"" enable=yes profile=any"; Flags: runhidden; StatusMsg: "Configuration du pare-feu…"
; Lance BobineTray (qui démarre lui-même BobineBackend)
; immédiatement après l'installation, sans attendre la prochaine session.
Filename: "{app}\BobineTray.exe"; Description: "Lancer Bobine"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Symétrique de la règle [Run] ci-dessus, retirée à la désinstallation.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Bobine"""; Flags: runhidden

; Note (aucune contrainte de migration) : cet
; installeur ne propose PAS de conserver/purger %ProgramData%\Bobine à la
; désinstallation — Inno Setup ne touche par défaut qu'à {app}
; (%ProgramFiles%\Bobine). Un utilisateur qui réinstalle retrouve donc ses
; données ; un utilisateur qui veut un nettoyage complet doit supprimer
; %ProgramData%\Bobine manuellement (à documenter dans le README).

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // Termine les processus Bobine actifs pour liberer les verrous de fichiers
  // lors d'une mise a jour ou reinstallation par-dessus une version existante
  Exec('taskkill.exe', '/F /IM BobineTray.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM BobineBackend.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
