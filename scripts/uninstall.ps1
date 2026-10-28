# uninstall.ps1 - cofa to, co zrobil instalator (uruchamiany przez odinstaluj.bat).
#
# Paczka nic nie instaluje w systemie, wiec do cofniecia sa tylko skroty i
# zapamietany port. Sterownika przejsciowki USB NIE ruszamy - to sterownik
# systemowy, moze go uzywac inne urzadzenie.

. "$PSScriptRoot\common.ps1"

$Host.UI.RawUI.WindowTitle = 'RPLIDAR - odinstalowanie'
Write-Host ""
Write-Host "  RPLIDAR - cofanie zmian" -ForegroundColor White

Step "Skroty na pulpicie"
$desk = [Environment]::GetFolderPath('Desktop')
$n = 0
foreach ($name in @('RPLIDAR - projekt TouchDesigner', 'RPLIDAR - sprawdz czujnik',
                    'RPLIDAR - folder')) {
    $p = Join-Path $desk ($name + '.lnk')
    if (Test-Path $p) { Remove-Item $p -Force; $n++ }
}
Ok "usunieto skrotow: $n"

Step "Zapamietany port"
$d = Join-Path $env:LOCALAPPDATA 'RPLidarTD'
if (Test-Path $d) {
    Remove-Item $d -Recurse -Force
    Ok "usunieto $d"
} else {
    Info "nic nie bylo zapisane"
}

Write-Host ""
Info "Sterownik przejsciowki USB (CP210x / CH340) zostaje - jest systemowy i moga go"
Info "uzywac inne urzadzenia. Caly folder paczki mozna teraz po prostu skasowac."
Write-Host ""
Write-Host "  Gotowe." -ForegroundColor Green
Pause-End
