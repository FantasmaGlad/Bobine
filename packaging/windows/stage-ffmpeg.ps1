# The immutable provider release and archive digests are reviewed together.
param(
    [Parameter(Mandatory = $true)][ValidateSet('x64', 'arm64')][string]$Architecture,
    [string]$Destination = 'backend/dist/Bobine'
)
$ErrorActionPreference = 'Stop'
$lock = Get-Content (Join-Path $PSScriptRoot 'ffmpeg.lock.json') -Raw | ConvertFrom-Json
$asset = $lock.$Architecture
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/$($lock.release)/$($asset.archive)"
$workspace = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory $workspace | Out-Null
try {
    $archive = Join-Path $workspace 'ffmpeg.zip'
    & curl.exe -fL --retry 3 --retry-delay 5 $url -o $archive
    if ($LASTEXITCODE -ne 0) { throw 'FFmpeg download failed' }
    if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.sha256) {
        throw 'FFmpeg archive SHA256 mismatch'
    }
    Expand-Archive -Path $archive -DestinationPath (Join-Path $workspace 'extracted')
    New-Item -ItemType Directory -Force $Destination | Out-Null
    foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
        $files = @(Get-ChildItem (Join-Path $workspace 'extracted') -Recurse -Filter $name)
        if ($files.Count -ne 1) { throw "Expected exactly one $name" }
        $stream = [System.IO.File]::OpenRead($files[0].FullName)
        $reader = [System.IO.BinaryReader]::new($stream)
        try {
            if ($reader.ReadUInt16() -ne 0x5a4d) { throw "Invalid DOS header: $name" }
            $stream.Position = 0x3c
            $peOffset = $reader.ReadUInt32()
            $stream.Position = $peOffset
            if ($reader.ReadUInt32() -ne 0x4550) { throw "Invalid PE header: $name" }
            if ($reader.ReadUInt16() -ne $asset.machine) { throw "Wrong $Architecture architecture: $name" }
        } finally { $reader.Dispose() }
        & $files[0].FullName -version
        if ($LASTEXITCODE -ne 0) { throw "$name cannot run on the $Architecture builder" }
        Copy-Item $files[0].FullName $Destination
    }
} finally {
    # Only disposable files created by this invocation are removed.
    Remove-Item -Recurse -Force $workspace
}
