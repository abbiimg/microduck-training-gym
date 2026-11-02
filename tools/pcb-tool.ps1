param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('kibot','ngspice','python','pytest','ceedling','renode','kicad-cli')]
    [string]$Tool,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$ToolArgs
)
# Paths passed to tools must use WSL/Linux syntax, e.g. /mnt/c/Users/...
& wsl.exe -d NVIDIA-Workbench -- /home/workbench/robotics/pcb-tools/bin/pcb-tool $Tool @ToolArgs
exit $LASTEXITCODE
