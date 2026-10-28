# find-port.ps1 - szuka portu COM, na ktorym odpowiada RPLIDAR.
# Wypisuje nazwe portu na standardowe wyjscie ("" gdy nie znalazl) i zapisuje
# ja do %LOCALAPPDATA%\RPLidarTD\port.txt, skad czyta ja komponent w TouchDesignerze.
#
# -Quiet  : bez komentarza na ekranie (do uzycia ze skryptu)
# -NoSave : nie zapisuj port.txt
param([switch]$Quiet, [switch]$NoSave)

. "$PSScriptRoot\common.ps1"
. "$PSScriptRoot\rplidar.ps1"

function Say($t) { if (-not $Quiet) { Info $t } }

$ports = Get-LivePorts
if ($ports.Count -eq 0) {
    if (-not $Quiet) {
        Warn "Nie widze zadnego portu COM. Lidar nie jest podlaczony albo brakuje sterownika przejsciowki."
    }
    Write-Output ''
    return
}

# Najpierw porty na przejsciowkach, ktore RPLIDAR-y zwykle maja (CP210x, CH340, FTDI).
$ranked = @()
$rest = @()
foreach ($c in $ports) {
    $dev = Get-PortDevice $c
    if (Test-LidarAdapter $dev) { $ranked += $c } else { $rest += $c }
}
$ranked += $rest

Say ("Porty do sprawdzenia: " + ($ranked -join ', '))

foreach ($c in $ranked) {
    Say "sprawdzam $c ..."
    $info = Test-LidarPort $c
    if ($info) {
        if (-not $Quiet) {
            Ok ("$c -> " + $info.Name + " (firmware " + $info.Firmware + ", hardware " + $info.Hardware + ")")
        }
        if (-not $NoSave) { Save-Port $c }
        Write-Output $c
        return
    }
}

if (-not $Quiet) {
    Warn "Zaden port nie odpowiedzial jak RPLIDAR."
    Info "Sprawdz: czy lidar sie kreci (slychac silnik), czy kabel USB jest w porcie, czy TouchDesigner"
    Info "nie trzyma juz portu (zamknij TD i powtorz) - patrz README, sekcja 'Typowe problemy'."
}
Write-Output ''
