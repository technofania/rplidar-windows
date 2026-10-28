# common.ps1 - wspolne funkcje skryptow paczki RPLIDAR
# (dot-source: . "$PSScriptRoot\common.ps1")

$script:Root = Split-Path -Parent $PSScriptRoot

function Step($t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  [OK] $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }
function Info($t) { Write-Host "       $t" }

function Pause-End {
    Write-Host ""
    Read-Host "Nacisnij Enter, aby zamknac okno" | Out-Null
}

function Fail($t) {
    Write-Host ""
    Write-Host "  [BLAD] $t" -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch {}
    Pause-End
    exit 1
}

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Ask-YesNo([string]$Question, [bool]$Default = $true) {
    $hint = if ($Default) { '[T/n]' } else { '[t/N]' }
    $a = Read-Host "$Question $hint"
    if ([string]::IsNullOrWhiteSpace($a)) { return $Default }
    $a = $a.Trim().ToLower()
    return $a.StartsWith('t') -or $a.StartsWith('y')
}

# Folder, w ktorym paczka zapisuje wykryty port (czyta go komponent w TouchDesignerze).
function Get-StateDir {
    $d = Join-Path $env:LOCALAPPDATA 'RPLidarTD'
    New-Item -ItemType Directory -Force $d | Out-Null
    return $d
}

function Save-Port([string]$Port) {
    [IO.File]::WriteAllText((Join-Path (Get-StateDir) 'port.txt'), $Port)
}

function Load-Port {
    $f = Join-Path (Get-StateDir) 'port.txt'
    if (Test-Path $f) { return ([IO.File]::ReadAllText($f)).Trim() }
    return $null
}

# ---------------------------------------------------------------- urzadzenia

# Porty szeregowe, ktore ISTNIEJA w tej chwili (nie wpisy-widma w rejestrze).
function Get-LivePorts {
    return @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object {
        if ($_ -match '(\d+)$') { [int]$Matches[1] } else { 9999 }
    })
}

# Opis urzadzenia USB stojacego za danym portem COM (albo $null).
function Get-PortDevice([string]$Port) {
    try {
        $all = Get-CimInstance Win32_PnPEntity -ErrorAction Stop |
               Where-Object { $_.Name -like "*($Port)*" }
        if ($all) { return $all[0] }
    } catch {}
    return $null
}

# Czy to przejsciowka, ktora RPLIDAR-y zwykle maja na pokladzie?
# CP2102 (Silicon Labs, VID_10C4) - A1/A2/A3 i wiekszosc zestawow USB.
# CH340 (VID_1A86) - czesc nowszych plytek i klonow.
# FTDI (VID_0403) - rzadziej.
function Test-LidarAdapter($dev) {
    if (-not $dev) { return $false }
    return ($dev.PNPDeviceID -match 'VID_10C4' -or
            $dev.PNPDeviceID -match 'VID_1A86' -or
            $dev.PNPDeviceID -match 'VID_0403')
}

# Urzadzenia USB bez sterownika (zolty wykrzyknik) - typowe, gdy brakuje CP210x.
function Get-BrokenUsbSerial {
    try {
        return @(Get-CimInstance Win32_PnPEntity -ErrorAction Stop | Where-Object {
            $_.ConfigManagerErrorCode -ne 0 -and
            ($_.PNPDeviceID -match 'VID_10C4' -or $_.PNPDeviceID -match 'VID_1A86' -or
             $_.PNPDeviceID -match 'VID_0403' -or $_.Name -match 'CP210|Serial')
        })
    } catch { return @() }
}
