param(
  [ValidateSet('stable', 'beta', 'canary')]
  [string]$Channel = 'stable',
  [switch]$Tor,
  [int]$TorPort = 9150
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($PSVersionTable.PSVersion.Major -lt 6) {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
}

$web = @{ UseBasicParsing = $true }
if ($Tor) {
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

$SigningKeyModuli = @(
  'tZWGj1cpMao6UGU83DwXax0YFD3JeJCnBC+8ckd+4caTWOeBScqiownN/mreLLbS4voEVsEVuh5wz9jnuOD4+b5iY2KjcSZxM6DNppKHygmk+hkPC2XhoAMt8XmwTynPStNSiMQFsjrzRi3NkWky8chduBnkJebpyqmWOum8n7+M7SYwNnCIjto48Swu+Sf3kHGueGVWEfdzjjAc4jBHZIRV/pIm9EM94XKVSrmGqJ4pUrEy2cGlPZU9G+DCWS+/+vXXkrGxH8+t1Y/lsBufmClrOhS04DfItnvhQIOEZalwfwtCc+TB3hGxQV9siYC3mPdA6Oe9O2tyNaYqZWzQBr+VoLNh0ytYH/VISLntg//0rxE/cY63VyIufZ8Z6L4TxF8Eoivm52rqsEbVhykhlYbd/euXj9Q/EkhulHtjm6qQqsafpZwvda5fOQcvlJvbVlsmrKUVsLtzcHWGd5dzvSzgk9RUMoN9axuKScjZrksUB/3eKBD10hrRyprzHwLV5Z597MIkreFXq7HtHfcZy3Cow98rmbxEJ6JL83ViCxw3T9VOn+3rUUqnDIP8x37BgDBFtWycEusAMp/GlNFcI8Jo2iUOMlm91K6Lq2+dUwYd1Ll+dDNaCFUUkt8gF/0KvchxqegSckTsTHzSErHJVRAdnbPHdyGsoehAbXvYn6U='
)

function Test-ReleaseSignature([byte[]]$Data, [string]$Armored) {
  $b64 = ($Armored -split "`r?`n" | Where-Object { $_ -and $_ -notmatch '^(-----|=|[A-Za-z]+: )' }) -join ''
  $p = [Convert]::FromBase64String($b64)
  $i = 1
  if ($p[0] -band 0x40) {
    if (($p[0] -band 0x3F) -ne 2) { return $false }
    $l = [int]$p[$i]; $i++
    if ($l -ge 192 -and $l -lt 224) { $l = (($l - 192) -shl 8) + $p[$i] + 192; $i++ }
    elseif ($l -eq 255) { $i += 4 }
  } else {
    if ((($p[0] -shr 2) -band 0x0F) -ne 2) { return $false }
    $i += @(1, 2, 4)[$p[0] -band 3]
  }
  $start = $i
  if ($p[$i] -ne 4 -or $p[$i + 1] -ne 0 -or $p[$i + 2] -ne 1) { return $false }
  $hashName = switch ($p[$i + 3]) { 8 { 'SHA256' } 10 { 'SHA512' } default { return $false } }
  $hashedLen = ([int]$p[$i + 4] -shl 8) + $p[$i + 5]
  $i += 6 + $hashedLen
  $unhashedLen = ([int]$p[$i] -shl 8) + $p[$i + 1]
  $i += 2 + $unhashedLen + 2
  $bits = ([int]$p[$i] -shl 8) + $p[$i + 1]
  $sig = [byte[]]$p[($i + 2)..($i + 1 + [math]::Ceiling($bits / 8))]

  $hashed = [byte[]]$p[$start..($start + 5 + $hashedLen)]
  $trailer = [byte[]](4, 0xFF) + [BitConverter]::GetBytes([uint32]$hashed.Length)[3..0]
  $hasher = if ($hashName -eq 'SHA256') { [Security.Cryptography.SHA256]::Create() } else { [Security.Cryptography.SHA512]::Create() }
  $digest = $hasher.ComputeHash([byte[]]($Data + $hashed + $trailer))

  foreach ($encoded in $SigningKeyModuli) {
    $modulus = [Convert]::FromBase64String($encoded)
    if ($sig.Length -gt $modulus.Length) { continue }
    $padded = [byte[]]::new($modulus.Length)
    [Array]::Copy($sig, 0, $padded, $modulus.Length - $sig.Length, $sig.Length)
    $rsa = [Security.Cryptography.RSA]::Create()
    $key = [Security.Cryptography.RSAParameters]::new()
    $key.Modulus = $modulus
    $key.Exponent = [byte[]](1, 0, 1)
    $rsa.ImportParameters($key)
    if ($rsa.VerifyHash($digest, $padded, [Security.Cryptography.HashAlgorithmName]::$hashName, [Security.Cryptography.RSASignaturePadding]::Pkcs1)) { return $true }
  }
  return $false
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
  Invoke-WebRequest "$base/SHA256SUMS.asc" -OutFile "$sums.asc" @web
  if (-not (Test-ReleaseSignature ([IO.File]::ReadAllBytes($sums)) (Get-Content "$sums.asc" -Raw))) {
    throw "Signature de SHA256SUMS invalide : installation annulée."
  }
  $line = Get-Content $sums | Where-Object { $_ -match "\s\*?$([regex]::Escape($name))\s*$" }
  if (-not $line) { throw "Aucune empreinte pour $name dans SHA256SUMS." }
  $expected = ($line -split '\s+')[0].ToUpper()
  if ((Get-FileHash $setup -Algorithm SHA256).Hash -ne $expected) { throw "Empreinte SHA-256 incorrecte pour $name : installation annulée." }
  $process = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Verb RunAs -Wait -PassThru
  if ($process.ExitCode -ne 0) { throw "L'installeur a échoué (code $($process.ExitCode))." }
  Write-Output "Bobine est installé. Lancez Bobine depuis le menu Démarrer, puis ouvrez http://127.0.0.1:1903."
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
