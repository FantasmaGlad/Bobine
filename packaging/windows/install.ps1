# Installe ou met à jour Bobine sous Windows (x64 ou ARM64) depuis GitHub Releases.
# Usage : irm https://github.com/FantasmaGlad/Bobine/releases/download/canary/install.ps1 | iex
# Autre canal : & ([scriptblock]::Create((irm https://github.com/FantasmaGlad/Bobine/releases/download/canary/install.ps1))) -Channel canary
# Par Tor (PowerShell 7.2+, Tor Browser ouvert) : & ([scriptblock]::Create((irm https://github.com/FantasmaGlad/Bobine/releases/download/canary/install.ps1 -Proxy socks5://127.0.0.1:9150))) -Tor
#   -Tor passe tous les téléchargements par le proxy SOCKS de Tor Browser (9150) ; -TorPort 9050 pour le service tor.
param(
  [ValidateSet('stable', 'beta', 'canary')]
  [string]$Channel = 'stable',
  [switch]$Tor,
  [int]$TorPort = 9150
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# Windows PowerShell 5.1 peut encore négocier TLS 1.0 par défaut sur une installation
# Windows 10 ancienne, que GitHub refuse ; forcer TLS 1.2 pour les appels de ce script.
if ($PSVersionTable.PSVersion.Major -lt 6) {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
}

$web = @{ UseBasicParsing = $true }
if ($Tor) {
  # SOCKS5 demande PowerShell 7.2+ (.NET 6) : 7.0 et 7.1 refusent le schéma socks5.
  if ($PSVersionTable.PSVersion -lt [version]'7.2') { throw "-Tor exige PowerShell 7.2 ou plus récent (pwsh) : https://aka.ms/powershell" }
  $web.Proxy = "socks5://127.0.0.1:$TorPort"
  try { $exit = Invoke-RestMethod 'https://check.torproject.org/api/ip' @web -TimeoutSec 60 }
  catch { throw "Tor ne répond pas sur 127.0.0.1:$TorPort (ouvrez Tor Browser, ou -TorPort 9050 pour le service tor)." }
  if (-not $exit.IsTor) { throw "Le proxy 127.0.0.1:$TorPort n'est pas une sortie Tor : téléchargements annulés." }
  Write-Output "Téléchargements par Tor (127.0.0.1:$TorPort)."
}

$cpu = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$arch = switch ($cpu) {
  'AMD64' { '' }
  'ARM64' { '-arm64' }
  default { throw "Système non pris en charge : $cpu (Bobine existe pour Windows x64 et ARM64)." }
}

$api = 'https://api.github.com/repos/FantasmaGlad/Bobine/releases'
if ($Channel -eq 'stable') {
  $release = Invoke-RestMethod "$api/latest" -Headers @{ 'User-Agent' = 'bobine-install' } @web
  $label = $release.tag_name.TrimStart('V', 'v')
} else {
  $release = Invoke-RestMethod "$api/tags/$Channel" -Headers @{ 'User-Agent' = 'bobine-install' } @web
  $label = $Channel
}
$name = "Bobine-Setup-$label$arch.exe"
$base = "https://github.com/FantasmaGlad/Bobine/releases/download/$($release.tag_name)"

$work = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $work | Out-Null
try {
  $setup = Join-Path $work $name
  $sums = Join-Path $work 'SHA256SUMS'
  Write-Output "Téléchargement de $name ($Channel)..."
  Invoke-WebRequest "$base/$name" -OutFile $setup @web
  Invoke-WebRequest "$base/SHA256SUMS" -OutFile $sums @web
  $line = Get-Content $sums | Where-Object { $_ -match "\s\*?$([regex]::Escape($name))\s*$" }
  if (-not $line) { throw "Aucune empreinte pour $name dans SHA256SUMS." }
  $expected = ($line -split '\s+')[0].ToUpper()
  if ((Get-FileHash $setup -Algorithm SHA256).Hash -ne $expected) { throw "Empreinte SHA-256 incorrecte pour $name : installation annulée." }
  # L'installeur demande l'élévation (installation pour tous les utilisateurs).
  $process = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Verb RunAs -Wait -PassThru
  if ($process.ExitCode -ne 0) { throw "L'installeur a échoué (code $($process.ExitCode))." }
  Write-Output "Bobine est installé. Lancez Bobine depuis le menu Démarrer, puis ouvrez http://127.0.0.1:1903."
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
