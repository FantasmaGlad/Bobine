# Installe ou met à jour Bobine sous Windows (x64 ou ARM64) depuis GitHub Releases.
# Usage : irm https://bobine.fit/install.ps1 | iex
# Autre canal : & ([scriptblock]::Create((irm https://bobine.fit/install.ps1))) -Channel canary
param(
  [ValidateSet('stable', 'beta', 'canary')]
  [string]$Channel = 'stable'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$arch = switch ($env:PROCESSOR_ARCHITECTURE) {
  'AMD64' { '' }
  'ARM64' { '-arm64' }
  default { throw "Système non pris en charge : $env:PROCESSOR_ARCHITECTURE (Bobine existe pour Windows x64 et ARM64)." }
}

$api = 'https://api.github.com/repos/FantasmaGlad/Bobine/releases'
if ($Channel -eq 'stable') {
  $release = Invoke-RestMethod "$api/latest" -Headers @{ 'User-Agent' = 'bobine-install' }
  $label = $release.tag_name.TrimStart('V', 'v')
} else {
  $release = Invoke-RestMethod "$api/tags/$Channel" -Headers @{ 'User-Agent' = 'bobine-install' }
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
  Invoke-WebRequest "$base/$name" -OutFile $setup -UseBasicParsing
  Invoke-WebRequest "$base/SHA256SUMS" -OutFile $sums -UseBasicParsing
  $line = Get-Content $sums | Where-Object { $_ -match "\s\*?$([regex]::Escape($name))\s*$" }
  if (-not $line) { throw "Aucune empreinte pour $name dans SHA256SUMS." }
  $expected = ($line -split '\s+')[0].ToUpper()
  if ((Get-FileHash $setup -Algorithm SHA256).Hash -ne $expected) { throw "Empreinte SHA-256 incorrecte pour $name : installation annulée." }
  # L'installeur demande l'élévation (installation pour tous les utilisateurs).
  $process = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Verb RunAs -Wait -PassThru
  if ($process.ExitCode -ne 0) { throw "L'installeur a échoué (code $($process.ExitCode))." }
  Write-Output "Bobine est installé : http://127.0.0.1:1903"
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
