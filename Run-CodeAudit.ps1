# CodeAudit 2.2 — read-only source and local Git history. Output outside the project.
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectPath,
    [string]$Previous,
    [switch]$NoPrevious,
    [switch]$NoEslint,
    [switch]$NoGit,
    [switch]$SkipVarInventory,
    [string[]]$Requirements,  # opcjonalny plik(i) z listą pakietów dla -PipAudit, także spoza projektu
    [switch]$PipAudit,        # sprawdza zależności w bazie podatności — WYMAGA INTERNETU
    [switch]$NoExtras,        # pomija lizard, vulture, bandit, duplikację i graf zależności
    [switch]$NoLizard,
    [switch]$NoVulture,
    [switch]$NoBandit,
    [switch]$NoDuplication,
    [switch]$NoDeps,
    [ValidateRange(1,5000)]
    [int]$GitMaxCommits = 800
)
$ErrorActionPreference = 'Stop'
$AuditScript = Join-Path $PSScriptRoot 'audit.py'
if (-not (Test-Path -LiteralPath $AuditScript -PathType Leaf)) {
    throw "Missing audit.py in $PSScriptRoot"
}
$Params = @($AuditScript, $ProjectPath, '--git-max-commits', [string]$GitMaxCommits)
if ($Previous) { $Params += @('--previous', $Previous) }
if ($NoPrevious) { $Params += '--no-previous' }
if ($NoEslint) { $Params += '--no-eslint' }
if ($NoGit) { $Params += '--no-git' }
if ($SkipVarInventory) { $Params += '--skip-var-inventory' }
if ($PipAudit) { $Params += '--pip-audit' }
foreach ($r in $Requirements) { $Params += @('--requirements', $r) }
if ($NoExtras) { $Params += '--no-extras' }
if ($NoLizard) { $Params += '--no-lizard' }
if ($NoVulture) { $Params += '--no-vulture' }
if ($NoBandit) { $Params += '--no-bandit' }
if ($NoDuplication) { $Params += '--no-duplication' }
if ($NoDeps) { $Params += '--no-deps' }
& python @Params
exit $LASTEXITCODE
