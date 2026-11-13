param([string]$Dir = (Join-Path $PSScriptRoot 'fixtures/release-signature'))
$ErrorActionPreference = 'Stop'

$script = Join-Path $PSScriptRoot '../../packaging/windows/install.ps1'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$null, [ref]$null)
$function = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-ReleaseSignature' }, $true)
$key = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -eq '$SigningKeyModuli' }, $true)
if (-not $function -or -not $key) { throw 'Test-ReleaseSignature ou $SigningKeyModuli introuvable dans install.ps1.' }
. ([scriptblock]::Create($key.Extent.Text + "`n" + $function.Extent.Text))

$data = [IO.File]::ReadAllBytes((Join-Path $Dir 'SHA256SUMS'))
$armored = Get-Content (Join-Path $Dir 'SHA256SUMS.asc') -Raw
if (-not (Test-ReleaseSignature $data $armored)) { throw "Signature de $Dir/SHA256SUMS refusée par install.ps1." }
$data[0] = $data[0] -bxor 1
if (Test-ReleaseSignature $data $armored) { throw 'Une liste altérée est acceptée par install.ps1.' }
Write-Output "install.ps1 : signature de $Dir/SHA256SUMS vérifiée, liste altérée refusée."
