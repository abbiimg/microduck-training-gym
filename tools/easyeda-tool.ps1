param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ToolArgs)
$exe='C:\Users\abbii\Documents\Codex\tools\lceda-pro-4.1.78\lceda-pro.exe'
if (!(Test-Path -LiteralPath $exe)) { throw "Native client missing: $exe" }
# The vendor's Windows CLI requires a pipe for stdout capture.
& $exe @ToolArgs | Out-String
exit $LASTEXITCODE
