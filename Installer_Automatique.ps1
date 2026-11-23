param([switch]$Desinstaller, [switch]$Statut, [switch]$Pause)

$ErrorActionPreference = "Stop"
$nom = "Trading MT5 - surveillance D1"

if ($Statut) {
    Get-ScheduledTask -TaskName $nom | Select-Object TaskName, State
    Get-ScheduledTaskInfo -TaskName $nom | Select-Object LastRunTime, LastTaskResult
    $fichierEtat = Join-Path $PSScriptRoot "automatique_etat.json"
    if (Test-Path -LiteralPath $fichierEtat) {
        $etat = Get-Content -LiteralPath $fichierEtat -Raw -Encoding UTF8 | ConvertFrom-Json
        $age = ([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($etat.heure)).TotalSeconds
        $etat | Select-Object mode, statut, heure, @{Name="AgeSecondes"; Expression={[Math]::Round($age)}}
    } else {
        Write-Host "Aucun rapport encore publie."
    }
    exit
}

if ($Pause) {
    Disable-ScheduledTask -TaskName $nom | Out-Null
    Stop-ScheduledTask -TaskName $nom
    exit
}

if ($Desinstaller) {
    Stop-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $nom -Confirm:$false
    exit
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
$script = Join-Path $PSScriptRoot "automatique.py"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Le projet doit être installé dans .venv."
}
$utilisateur = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument ('"{0}"' -f $script) -WorkingDirectory $PSScriptRoot
$declencheur = New-ScheduledTaskTrigger -AtLogOn -User $utilisateur
$principal = New-ScheduledTaskPrincipal -UserId $utilisateur -LogonType Interactive -RunLevel Limited
$reglages = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Stop-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $nom -Action $action -Trigger $declencheur -Principal $principal -Settings $reglages -Force | Out-Null
Start-ScheduledTask -TaskName $nom
Write-Host "Surveillance démarrée. Ouvre Ouvrir_Trading.vbs pour voir le rapport."
