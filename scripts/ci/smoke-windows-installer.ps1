<#
Cycle de vie réel de l'installeur Inno Setup dans la CI Windows (x64 et ARM64) :
  Install    installation silencieuse dans un dossier de test, journal conservé ;
  Verify     arborescence installée identique à celle de PyInstaller, clé de
             désinstallation, règle de pare-feu ;
  Uninstall  désinstallation silencieuse, puis retrait vérifié (dossier, clé,
             règle de pare-feu, raccourci de démarrage).
Le lancement du backend installé se fait avec smoke-windows-backend.ps1.
Aucune signature n'est exigée : SmartScreen n'est pas exercé par la CI.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Install', 'Verify', 'Uninstall', 'Logs')][string]$Action,
    [Parameter(Mandatory)][string]$InstallDir,
    [Parameter(Mandatory)][string]$LogDir,
    [string]$Installer,
    [string]$DistDir,
    [string]$ExpectedVersion
)
$ErrorActionPreference = 'Stop'

$appId = '{B0B1AE00-C1AE-4A00-9A11-B0B1AE000001}_is1'
$uninstallKeys = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$appId",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\$appId"
)
$startupShortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'Bobine.lnk'
$installLog = Join-Path $LogDir 'install.log'
$uninstallLog = Join-Path $LogDir 'uninstall.log'

function Get-UninstallEntry {
    foreach ($key in $uninstallKeys) {
        if (Test-Path $key) { return Get-ItemProperty $key }
    }
}

function Test-FirewallRule {
    & netsh.exe advfirewall firewall show rule name=Bobine *> $null
    return ($LASTEXITCODE -eq 0)
}

function Test-MachinePath([string]$Dir) {
    $paths = [Environment]::GetEnvironmentVariable('Path', 'Machine') -split ';'
    return [bool]($paths | Where-Object { $_.TrimEnd('\') -ieq $Dir.TrimEnd('\') })
}

function Invoke-Silent([string]$File, [string[]]$Arguments, [string]$What) {
    # Les messages de l'installeur et du désinstalleur passent par le journal /LOG, pas par la console.
    $process = Start-Process -FilePath $File -ArgumentList $Arguments -Wait -PassThru
    Write-Host "$What : code de sortie $($process.ExitCode)"
    if ($process.ExitCode -ne 0) { throw "$What a échoué (code $($process.ExitCode))" }
}

switch ($Action) {
    'Install' {
        if (-not (Test-Path -LiteralPath $Installer)) { throw "Installeur introuvable : $Installer" }
        if (Test-Path -LiteralPath $InstallDir) { throw "Le dossier de test existe déjà : $InstallDir" }
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        Write-Host ("Installeur : {0} ({1:N1} Mio)" -f $Installer, ((Get-Item -LiteralPath $Installer).Length / 1MB))
        Invoke-Silent (Resolve-Path -LiteralPath $Installer).Path @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$InstallDir`"", "/LOG=`"$installLog`""
        ) "Installation silencieuse"
    }

    'Verify' {
        $problems = New-Object System.Collections.Generic.List[string]
        if (-not (Test-Path -LiteralPath $InstallDir)) { throw "Dossier d'installation absent : $InstallDir" }
        $installRoot = (Resolve-Path -LiteralPath $InstallDir).Path.TrimEnd('\')

        # Tout ce que PyInstaller a produit (dont les sidecars ajoutés après) doit être installé, à la même taille.
        $expected = @()
        if ($DistDir) {
            $distRoot = (Resolve-Path -LiteralPath $DistDir).Path.TrimEnd('\')
            $expected = @(Get-ChildItem -Recurse -File -Force -LiteralPath $distRoot)
            foreach ($file in $expected) {
                $relative = $file.FullName.Substring($distRoot.Length + 1)
                $target = Join-Path $installRoot $relative
                if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
                    $problems.Add("manquant : $relative")
                } elseif ((Get-Item -LiteralPath $target).Length -ne $file.Length) {
                    $problems.Add("taille différente : $relative")
                }
            }
        }
        foreach ($required in 'BobineBackend.exe', 'BobineTray.exe', 'bobine.exe', 'bobine-devices.exe', 'unins000.exe', 'unins000.dat') {
            if (-not (Test-Path -LiteralPath (Join-Path $installRoot $required) -PathType Leaf)) {
                $problems.Add("fichier obligatoire absent : $required")
            }
        }
        Write-Host ("Arborescence : {0} fichiers attendus (PyInstaller), {1} fichiers installés" -f $expected.Count,
            (Get-ChildItem -Recurse -File -Force -LiteralPath $installRoot).Count)

        $entry = Get-UninstallEntry
        if (-not $entry) {
            $problems.Add("clé de désinstallation $appId absente")
        } else {
            Write-Host "Clé de désinstallation : $($entry.DisplayName) $($entry.DisplayVersion)"
            if ($ExpectedVersion -and $entry.DisplayVersion -ne $ExpectedVersion) {
                $problems.Add("version installée $($entry.DisplayVersion) au lieu de $ExpectedVersion")
            }
        }
        if (-not (Test-FirewallRule)) { $problems.Add('règle de pare-feu "Bobine" absente') }
        # Une seule règle (pas de copie à chaque mise à jour), limitée aux réseaux locaux : jamais « Any ». Windows rend les plages
        # avec un masque (10.0.0.0/255.0.0.0) ou en intervalle, pas en notation CIDR.
        $rules = @(Get-NetFirewallRule -DisplayName 'Bobine' -ErrorAction SilentlyContinue)
        if ($rules.Count -ne 1) { $problems.Add("$($rules.Count) règles de pare-feu « Bobine », 1 attendue") }
        foreach ($rule in $rules) {
            $remote = @(($rule | Get-NetFirewallAddressFilter).RemoteAddress)
            if ($remote -contains 'Any' -or -not @($remote | Where-Object { $_ -like '10.0.0.0/*' -or $_ -like '10.0.0.0-*' })) {
                $problems.Add("règle de pare-feu ouverte au-delà du réseau local : $($remote -join ', ')")
            }
        }
        if (-not (Test-Path -LiteralPath $startupShortcut)) { $problems.Add("raccourci de démarrage absent : $startupShortcut") }
        if (-not (Test-MachinePath $installRoot)) { $problems.Add("$installRoot absent du PATH système (commande bobine)") }
        $cli = Join-Path $installRoot 'bobine.exe'
        if (Test-Path -LiteralPath $cli) {
            $version = (& $cli --version 2>&1 | Out-String).Trim()
            Write-Host "Commande bobine : $version (code $LASTEXITCODE)"
            if ($LASTEXITCODE -ne 0 -or $version -notmatch '^bobine ') { $problems.Add("bobine.exe --version a échoué : $version") }
        }

        if ($problems.Count -gt 0) {
            $problems | ForEach-Object { Write-Host "ERREUR : $_" }
            throw "$($problems.Count) écart(s) entre l'installation et l'arborescence PyInstaller"
        }
        Write-Host "Arborescence installée conforme."
    }

    'Uninstall' {
        $uninstaller = Join-Path $InstallDir 'unins000.exe'
        if (-not (Test-Path -LiteralPath $uninstaller)) { throw "Désinstalleur absent : $uninstaller" }
        Invoke-Silent $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$uninstallLog`"") "Désinstallation silencieuse"

        # Le désinstalleur d'Inno Setup se relance depuis %TEMP% : attendre l'effacement effectif.
        for ($i = 0; $i -lt 60 -and ((Test-Path -LiteralPath $InstallDir) -or (Get-UninstallEntry)); $i++) {
            Start-Sleep -Seconds 1
        }
        $problems = New-Object System.Collections.Generic.List[string]
        if (Test-Path -LiteralPath $InstallDir) {
            $left = Get-ChildItem -Recurse -Force -LiteralPath $InstallDir | Select-Object -First 20 -ExpandProperty FullName
            $problems.Add("le dossier $InstallDir existe encore : " + ($left -join ', '))
        }
        if (Get-UninstallEntry) { $problems.Add('la clé de désinstallation existe encore') }
        if (Test-FirewallRule) { $problems.Add('la règle de pare-feu "Bobine" existe encore') }
        if (Test-Path -LiteralPath $startupShortcut) { $problems.Add("le raccourci de démarrage existe encore : $startupShortcut") }
        if (Test-MachinePath $InstallDir) { $problems.Add("$InstallDir est resté dans le PATH système") }
        if ($problems.Count -gt 0) {
            $problems | ForEach-Object { Write-Host "ERREUR : $_" }
            throw "Désinstallation incomplète ($($problems.Count) reste(s))"
        }
        Write-Host "Désinstallation complète : dossier, clé, règle de pare-feu et raccourci retirés."
    }

    'Logs' {
        foreach ($log in $installLog, $uninstallLog, (Join-Path $LogDir 'backend_err.log'), (Join-Path $LogDir 'backend_out.log')) {
            if (Test-Path -LiteralPath $log) {
                Write-Host "=== $log (200 dernières lignes) ==="
                Get-Content -LiteralPath $log -Tail 200
            }
        }
    }
}

# Le code de sortie ne doit pas être celui de la dernière commande native (netsh renvoie 1 sans règle).
exit 0
