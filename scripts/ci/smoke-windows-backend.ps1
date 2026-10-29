<#
Sonde de santé du backend Windows : lance BobineBackend.exe, attend HTTP 200 sur /api/health,
arrête le processus et libère le port. Partagée par les jobs windows-build et windows-build-arm64
(sonde de l'arborescence PyInstaller, puis de l'application installée par Inno Setup).

Le port d'écoute n'est pas imposé : sans -Port, la sonde choisit un port libre, le transmet par
BOBINE_PORT avec BOBINE_PORT_STRICT=1 (aucun repli silencieux), refuse de démarrer si un autre
processus écoute déjà dessus et vérifie que le processus lancé est bien celui qui répond.
Avec -DataRoot, elle contrôle aussi que le fichier d'exécution du backend publie ce port.
-DataRoot isole les données : le backend les range sous %ProgramData%\Bobine, la variable est donc
redéfinie pour le seul processus lancé.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Exe,
    [string]$LogDir,
    [string]$DataRoot,
    [int]$Port = 0,
    [int]$Attempts = 20
)
$ErrorActionPreference = 'Stop'

function Get-PortListeners([int]$Number) {
    [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
        Where-Object { $_.Port -eq $Number }
}

function Get-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, 0)
    $listener.Start()
    try { ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port } finally { $listener.Stop() }
}
if ($Port -eq 0) { $Port = Get-FreePort }

$Exe = (Resolve-Path -LiteralPath $Exe).Path
if (-not $LogDir) { $LogDir = Split-Path -Parent $Exe }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$errLog = Join-Path $LogDir 'backend_err.log'
$outLog = Join-Path $LogDir 'backend_out.log'
Remove-Item -Force -ErrorAction SilentlyContinue $errLog, $outLog

if (Get-PortListeners $Port) {
    throw "Le port $Port est déjà occupé avant le lancement de $Exe"
}

$previousProgramData = $env:ProgramData
$previousPort = $env:BOBINE_PORT
$previousStrict = $env:BOBINE_PORT_STRICT
$env:BOBINE_PORT = "$Port"
$env:BOBINE_PORT_STRICT = '1'
if ($DataRoot) {
    New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
    $env:ProgramData = $DataRoot
}
try {
    $proc = Start-Process -FilePath $Exe -WorkingDirectory (Split-Path -Parent $Exe) `
        -RedirectStandardError $errLog -RedirectStandardOutput $outLog -PassThru
} finally {
    $env:ProgramData = $previousProgramData
    $env:BOBINE_PORT = $previousPort
    $env:BOBINE_PORT_STRICT = $previousStrict
}

$ready = $false
$reason = "aucune réponse HTTP 200 après $Attempts essais"
for ($i = 0; $i -lt $Attempts; $i++) {
    Start-Sleep -Seconds 1
    if ($proc.HasExited) {
        $reason = "le processus s'est arrêté (code $($proc.ExitCode)) avant de répondre"
        break
    }
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $running = (Get-Process -Id $proc.Id -ErrorAction Stop).Path
            if ($running -ne $Exe) {
                $reason = "la réponse ne vient pas du binaire attendu ($running au lieu de $Exe)"
                break
            }
            if ($DataRoot) {
                $runtimeFile = Join-Path $DataRoot 'Bobine\backend-runtime.json'
                $published = $null
                try { $published = (Get-Content -Raw -LiteralPath $runtimeFile | ConvertFrom-Json).port } catch { }
                if ($published -ne $Port) {
                    $reason = "le fichier d'exécution $runtimeFile publie '$published' au lieu de $Port"
                    break
                }
            }
            $ready = $true
            Write-Host "Backend opérationnel sur le port $Port ($Exe) : $($response.Content)"
            break
        }
    } catch {
        # Attente de disponibilité
    }
}

if (-not $ready) {
    Write-Host "=== Échec : $reason ==="
}
if ($DataRoot) {
    Write-Host "=== Données isolées sous $DataRoot ==="
    Get-ChildItem -Recurse -Force -ErrorAction SilentlyContinue $DataRoot | Select-Object -First 40 FullName, Length | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
}
if (-not $ready) {
    Write-Host "=== Backend stderr ==="
    if (Test-Path $errLog) { Get-Content $errLog }
    Write-Host "=== Backend stdout ==="
    if (Test-Path $outLog) { Get-Content $outLog }
}

# Arrêt de l'arbre de processus, puis attente de la libération du port : le désinstalleur
# ou la sonde suivante ne doivent trouver ni verrou de fichier ni port occupé.
if (-not $proc.HasExited) {
    & taskkill.exe /F /T /PID $proc.Id | Out-Null
    $proc.WaitForExit(10000) | Out-Null
}
for ($i = 0; $i -lt 10 -and (Get-PortListeners $Port); $i++) { Start-Sleep -Seconds 1 }
if (Get-PortListeners $Port) {
    Write-Host "Le port $Port reste occupé après l'arrêt du backend"
    exit 1
}
if (-not $ready) { exit 1 }
exit 0
