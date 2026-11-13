#define MyAppName "Bobine"
#ifndef MyAppVersion
  #define MyAppVersion "5.2.0"
#endif
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
DefaultDirName={autopf}\Bobine
DefaultGroupName=Bobine
PrivilegesRequired=admin
ChangesEnvironment=yes
OutputDir=..\..\dist-installer
OutputBaseFilename=Bobine-Setup-{#MyOutputVersion}{#MyOutputSuffix}
Compression=lzma2
SolidCompression=yes
LicenseFile=..\..\LICENSE
SetupIconFile={#MyDistDir}\bobine.ico
UninstallDisplayIcon={app}\BobineTray.exe
CloseApplications=yes
CloseApplicationsFilter=*Bobine*.exe
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; modules compiles d'une ancienne installation retires avant extraction
Type: files; Name: "{app}\*.pyd"
Type: files; Name: "{app}\*.dll"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}'))

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\BobineTray.exe"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\BobineTray.exe"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\BobineTray.exe"; Parameters: "--startup"

[Run]
; regle liee au programme : couvre aussi le port de repli ; l'ancienne est retiree d'abord
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Bobine"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Bobine"" dir=in action=allow program=""{app}\BobineBackend.exe"" enable=yes profile=any remoteip=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10,fc00::/7,fe80::/10"; Flags: runhidden; StatusMsg: "Configuration du pare-feu…"
Filename: "{app}\BobineTray.exe"; Description: "Lancer Bobine"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Bobine"""; Flags: runhidden

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // Termine les processus Bobine actifs pour liberer les verrous de fichiers
  // lors d'une mise a jour ou reinstallation par-dessus une version existante
  Exec('taskkill.exe', '/F /IM BobineTray.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM bobine.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM BobineBackend.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

const
  EnvironmentKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

function NormalizeDir(Dir: String): String;
begin
  // Une entrée de PATH peut avoir été saisie avec une barre finale ; la racine d'un lecteur (C:\) la garde.
  Result := Dir;
  while (Length(Result) > 3) and (Copy(Result, Length(Result), 1) = '\') do
    Delete(Result, Length(Result), 1);
end;

function PathEntryPosition(Paths, Dir: String): Integer;
var
  Haystack, Needle: String;
begin
  Needle := Uppercase(NormalizeDir(Dir));
  Haystack := ';' + Uppercase(Paths) + ';';
  Result := Pos(';' + Needle + ';', Haystack);
  if Result = 0 then
    Result := Pos(';' + Needle + '\;', Haystack);
end;

function NeedsAddPath(Dir: String): Boolean;
var
  Paths: String;
begin
  if not RegQueryStringValue(HKLM, EnvironmentKey, 'Path', Paths) then
  begin
    Result := True;
    exit;
  end;
  Result := PathEntryPosition(Paths, Dir) = 0;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Paths, Dir: String;
  Position, EntryLength: Integer;
begin
  // Retire le dossier de Bobine du PATH, entrée exacte seulement (un dossier voisin comme ...\Bobine2 reste), sans
  // toucher aux autres entrées. Une barre finale dans le PATH ne doit pas empêcher le retrait.
  if CurUninstallStep <> usPostUninstall then
    exit;
  if not RegQueryStringValue(HKLM, EnvironmentKey, 'Path', Paths) then
    exit;
  Dir := ExpandConstant('{app}');
  Position := PathEntryPosition(Paths, Dir);
  if Position = 0 then
    exit;
  Paths := ';' + Paths + ';';
  EntryLength := Length(NormalizeDir(Dir)) + 1;
  if Copy(Paths, Position + EntryLength, 1) = '\' then
    EntryLength := EntryLength + 1;
  Delete(Paths, Position, EntryLength);
  Paths := Copy(Paths, 2, Length(Paths) - 2);
  RegWriteExpandStringValue(HKLM, EnvironmentKey, 'Path', Paths);
end;
