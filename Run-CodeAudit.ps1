# Windows PowerShell helper script. Example:
# .\Run-CodeAudit.ps1 -ProjectPath "C:\path\to\your-project"
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectPath
)
$ErrorActionPreference = 'Stop'
$AuditScript = Join-Path $PSScriptRoot 'audit.py'
if (-not (Test-Path -LiteralPath $AuditScript -PathType Leaf)) {
    throw "Missing audit.py in $PSScriptRoot"
}
& python $AuditScript $ProjectPath
exit $LASTEXITCODE
