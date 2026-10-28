# install.ps1 - instalator paczki RPLIDAR (uruchamiany przez INSTALUJ.bat).
#
# Paczka nie instaluje Pythona ani zadnych pakietow - caly kod czujnika siedzi
# w komponencie TouchDesignera, a diagnostyka jest w PowerShellu. Instalator ma
# wiec tylko cztery zadania: sprawdzic sterownik przejsciowki USB, znalezc port,
# sprawdzic TouchDesignera i zrobic skroty. Dlatego nie potrzebuje administratora.
param([switch]$NoShortcuts)

. "$PSScriptRoot\common.ps1"
. "$PSScriptRoot\rplidar.ps1"

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
Set-Location $Root
try { Start-Transcript -Path (Join-Path $Root 'install.log') -Force | Out-Null } catch {}

$Host.UI.RawUI.WindowTitle = 'Instalator RPLIDAR'
Write-Host ""
Write-Host "  RPLIDAR dla TouchDesignera - instalacja" -ForegroundColor White
Write-Host "  Folder: $Root"

# --- 0. czy to na pewno rozpakowany folder ---
if ($Root -match '\\AppData\\Local\\Temp\\' -or $Root -match '\.zip\\') {
    Fail "Uruchamiasz instalator z wnetrza archiwum ZIP. Najpierw rozpakuj (prawy klik na ZIP > Wyodrebnij wszystko), potem uruchom INSTALUJ.bat z rozpakowanego folderu."
}
Get-ChildItem $Root -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue

# --- 1. sterownik przejsciowki USB ---
Step "1/4 Sterownik przejsciowki USB"
$broken = Get-BrokenUsbSerial
$live = Get-LivePorts
if ($broken.Count -gt 0) {
    Warn "Jest urzadzenie USB bez dzialajacego sterownika:"
    foreach ($b in $broken) { Info ("  " + $b.Name + "   [" + $b.PNPDeviceID + "]") }
    Write-Host ""
    if ($broken[0].PNPDeviceID -match 'VID_1A86') {
        Info "To przejsciowka CH340. Sterownik: https://www.wch-ic.com/downloads/CH341SER_EXE.html"
    } else {
        Info "To prawie na pewno przejsciowka Silicon Labs CP210x (tak ma A1/A2/A3)."
        Info "Windows 10/11 pobiera ten sterownik sam z Windows Update, gdy komputer ma internet."
        Info "Jesli nie ma - sterownik 'CP210x Universal Windows Driver' jest tutaj:"
        Info "  https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers"
    }
    Write-Host ""
    Info "Co zrobic: podlacz internet, wyjmij i wloz USB, odczekaj minute, uruchom INSTALUJ.bat ponownie."
    Info "Instalacja leci dalej - reszta kroków nie wymaga sterownika."
} elseif ($live.Count -eq 0) {
    Warn "Nie widze zadnego portu COM."
    Info "Lidar nie jest podlaczony, albo kabel USB jest tylko do ladowania (bez zyl danych)."
} else {
    $adapters = @($live | Where-Object { Test-LidarAdapter (Get-PortDevice $_) })
    if ($adapters.Count -gt 0) {
        foreach ($c in $adapters) { Ok (Get-PortDevice $c).Name }
    } else {
        Ok ("porty COM: " + ($live -join ', '))
        Info "Zadna z przejsciowek nie wyglada na typowa dla RPLIDAR-a, ale sprawdze wszystkie."
    }
}

# --- 2. szukanie lidaru ---
Step "2/4 Szukam lidaru"
$port = ''
if ($live.Count -gt 0) {
    $port = (& "$PSScriptRoot\find-port.ps1" | Select-Object -Last 1)
}
if ($port) {
    $info = Test-LidarPort $port
    if ($info) {
        Ok ("$port -> " + $info.Name + ", firmware " + $info.Firmware)
        Save-Port $port
    }
} else {
    Warn "Nie znalazlem RPLIDAR-a."
    Info "Najczestsze przyczyny: brak zasilania (glowica musi sie krecic), kabel USB bez danych,"
    Info "port zajety przez inny program, brak sterownika przejsciowki."
    Info "Komponent w TouchDesignerze i tak ma Port = auto - znajdzie czujnik sam, gdy go podlaczysz."
}

# --- 3. TouchDesigner ---
Step "3/4 TouchDesigner"
$td = $null
foreach ($base in @("$env:ProgramFiles\Derivative", "${env:ProgramFiles(x86)}\Derivative")) {
    if (Test-Path $base) {
        $cand = Get-ChildItem $base -Directory -Filter 'TouchDesigner*' -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending | Select-Object -First 1
        if ($cand) {
            $exe = Join-Path $cand.FullName 'bin\TouchDesigner.exe'
            if (Test-Path $exe) { $td = $exe; break }
        }
    }
}
if ($td) {
    Ok ("znaleziony: " + $td)
} else {
    Warn "Nie znalazlem TouchDesignera w Program Files."
    Info "Pobierz darmowa wersje Non-Commercial: https://derivative.ca/download"
    Info "Paczka wymaga wersji 2022.20000 lub nowszej (testowana na 2025.32460)."
}

# --- 4. skroty ---
Step "4/4 Skroty na pulpicie"
if ($NoShortcuts) {
    Info "Pominieto (parametr -NoShortcuts)."
} else {
    try {
        $desk = [Environment]::GetFolderPath('Desktop')
        $ws = New-Object -ComObject WScript.Shell
        $links = @(
            @{ Name = 'RPLIDAR - projekt TouchDesigner'; Target = 'td\RPLidar.toe'; Icon = 'shell32.dll,13' },
            @{ Name = 'RPLIDAR - sprawdz czujnik';       Target = 'sprawdz-lidar.bat'; Icon = 'shell32.dll,23' },
            @{ Name = 'RPLIDAR - folder';                Target = '';                  Icon = 'shell32.dll,3' }
        )
        foreach ($l in $links) {
            $target = if ($l.Target) { Join-Path $Root $l.Target } else { $Root }
            if ($l.Target -and -not (Test-Path $target)) { continue }
            $s = $ws.CreateShortcut((Join-Path $desk ($l.Name + '.lnk')))
            $s.TargetPath = $target
            $s.WorkingDirectory = $Root
            $s.IconLocation = "$env:SystemRoot\System32\$($l.Icon)"
            $s.Save()
        }
        Ok "Utworzono skroty na pulpicie"
    } catch {
        Warn ("Nie udalo sie utworzyc skrotow: " + $_.Exception.Message)
    }
}

Write-Host ""
Write-Host "  Gotowe." -ForegroundColor Green
if ($port) {
    Write-Host "  Lidar na porcie $port. Otworz 'RPLIDAR - projekt TouchDesigner' z pulpitu."
} else {
    Write-Host "  Podlacz lidar i uruchom 'sprawdz-lidar.bat', potem otworz projekt z folderu td\."
}
Write-Host "  Szczegoly i rozwiazania problemow: README.md"
try { Stop-Transcript | Out-Null } catch {}
Pause-End
