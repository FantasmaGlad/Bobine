# Contrôle la vérification de signature de packaging/windows/install.ps1 sans l'exécuter : la fonction et le module de
# la sous-clé sont extraits par l'analyseur PowerShell. Une liste signée doit être acceptée, la même altérée d'un octet
# refusée. Sans argument : listes publiées de référence ; avec un dossier : SHA256SUMS fraîchement signée d'une release,
# ce qui arrête la publication si la sous-clé de signature ne correspond plus à celle épinglée dans install.ps1.
param([string]$Dir = (Join-Path $PSScriptRoot 'fixtures/release-signature'))
$ErrorActionPreference = 'Stop'

$script = Join-Path $PSScriptRoot '../../packaging/windows/install.ps1'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$null, [ref]$null)
$function = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-ReleaseSignature' }, $true)
$key = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -eq '$SigningKeyModulus' }, $true)
if (-not $function -or -not $key) { throw 'Test-ReleaseSignature ou $SigningKeyModulus introuvable dans install.ps1.' }
. ([scriptblock]::Create($key.Extent.Text + "`n" + $function.Extent.Text))

$data = [IO.File]::ReadAllBytes((Join-Path $Dir 'SHA256SUMS'))
$armored = Get-Content (Join-Path $Dir 'SHA256SUMS.asc') -Raw
if (-not (Test-ReleaseSignature $data $armored)) { throw "Signature de $Dir/SHA256SUMS refusée par install.ps1." }
$data[0] = $data[0] -bxor 1
if (Test-ReleaseSignature $data $armored) { throw 'Une liste altérée est acceptée par install.ps1.' }
Write-Output "install.ps1 : signature de $Dir/SHA256SUMS vérifiée, liste altérée refusée."
