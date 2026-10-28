# test-lidar.ps1 - diagnostyka RPLIDAR-a (uruchamiana przez sprawdz-lidar.bat).
# Czysty PowerShell: dziala takze wtedy, gdy nic jeszcze nie jest zainstalowane.
param([string]$Port = '', [double]$Seconds = 4.0)

. "$PSScriptRoot\common.ps1"
. "$PSScriptRoot\rplidar.ps1"

$Host.UI.RawUI.WindowTitle = 'RPLIDAR - diagnostyka'
Write-Host ""
Write-Host "  RPLIDAR - diagnostyka" -ForegroundColor White

# --- 1. porty i przejsciowka ---
Step "1/4 Porty COM"
$live = Get-LivePorts
if ($live.Count -eq 0) {
    Warn "Brak jakiegokolwiek portu COM w systemie."
    $broken = Get-BrokenUsbSerial
    if ($broken.Count -gt 0) {
        Warn "Jest urzadzenie USB bez sterownika:"
        foreach ($b in $broken) { Info ("  " + $b.Name + "  [" + $b.PNPDeviceID + "]") }
        Info "To zwykle brak sterownika CP210x. Uruchom INSTALUJ.bat - podpowie, co pobrac."
    } else {
        Info "Lidar nie jest podlaczony albo kabel USB jest tylko do ladowania (bez danych)."
    }
    Pause-End
    exit 1
}
foreach ($c in $live) {
    $dev = Get-PortDevice $c
    $name = if ($dev) { $dev.Name } else { $c }
    if (Test-LidarAdapter $dev) { Ok $name } else { Info $name }
}

# --- 2. wybor portu ---
Step "2/4 Szukam lidaru"
if (-not $Port) { $Port = Load-Port }
$info = $null
if ($Port -and ($live -contains $Port)) {
    Info "probuje zapamietany/podany port $Port"
    $info = Test-LidarPort $Port
    if (-not $info) { Warn "$Port nie odpowiada - szukam dalej"; $Port = '' }
}
if (-not $info) {
    $Port = (& "$PSScriptRoot\find-port.ps1" -Quiet | Select-Object -Last 1)
    if ($Port) { $info = Test-LidarPort $Port }
}
if (-not $info) {
    Warn "Nie znalazlem RPLIDAR-a na zadnym porcie."
    Info "Najczestsze przyczyny, po kolei:"
    Info "  1. TouchDesigner (albo inny program) trzyma port - port COM jest na wylacznosc. Zamknij TD."
    Info "  2. Lidar nie ma zasilania - silnik musi sie krecic (slychac szum, widac obracajaca sie glowice)."
    Info "     A2/A3 zasila sie z USB; A1 i S1 czesto potrzebuja osobnego 5 V."
    Info "  3. Kabel USB bez zyl danych (kabel 'do ladowania')."
    Info "  4. Brak sterownika przejsciowki - uruchom INSTALUJ.bat."
    Pause-End
    exit 1
}
Ok ("Port: $Port")
Ok ($info.Name + "  firmware " + $info.Firmware + ", hardware " + $info.Hardware)
Info ("numer seryjny: " + $info.Serial)
Save-Port $Port

# --- 3. stan ---
Step "3/4 Stan czujnika"
$p = $null
try {
    $p = Open-Lidar $Port
    $h = Get-LidarHealth $p
    if ($h) {
        if ($h.Status -eq 0) { Ok ("health: " + $h.Text) }
        elseif ($h.Status -eq 1) { Warn ("health: " + $h.Text + " (kod " + $h.Error + ")") }
        else {
            Warn ("health: " + $h.Text + " (kod " + $h.Error + ")")
            Info "Odlacz USB na 5 s i podlacz ponownie."
        }
    } else {
        Warn "Brak odpowiedzi na GET_HEALTH."
    }

    # --- 4. skan ---
    Step "4/4 Odbior danych ($Seconds s)"
    Info "lidar musi sie krecic..."
    $s = Measure-LidarScan $p $Seconds
    if (-not $s) {
        Warn "Lidar nie wystartowal skanu (brak deskryptora odpowiedzi)."
        Info "Zdarza sie, gdy silnik stoi. Sprawdz zasilanie i powtorz."
    } else {
        Ok ("probek: " + $s.Samples + " (" + $s.PerSecond + "/s), z odbiciem: " + $s.Valid)
        Ok ("obrotow: " + $s.Revs + ", ~" + $s.Rpm + " rpm")
        Ok ("pokrycie kata: " + $s.Coverage + "% z 360 stopni")
        Info ("odleglosci: " + $s.MinMm + " - " + $s.MaxMm + " mm")
        if ($s.Bad -gt 0) { Info ("odrzuconych bajtow: " + $s.Bad + " (kilka na start to norma)") }
        Write-Host ""
        if ($s.Valid -lt 100) {
            Warn "Bardzo malo odbic. Lidar kreci sie, ale prawie nic nie widzi."
            Info "Czujnik za blisko sciany (< 15 cm) albo wszystko wokol jest czarne/lustrzane/szklane."
        } elseif ($s.Coverage -lt 50) {
            Warn "Lidar widzi tylko czesc otoczenia ($($s.Coverage)%)."
            Info "Normalne, jesli stoi w kacie albo przy scianie. Przy otwartej przestrzeni - sprawdz, czy"
            Info "cos nie zaslania glowicy (tasma, kabel, obudowa)."
        } else {
            Write-Host "  Czujnik dziala poprawnie." -ForegroundColor Green
        }
        if ($s.Rpm -gt 0 -and $s.Rpm -lt 200) {
            Warn "Niskie obroty ($($s.Rpm) rpm) - zwykle slabe zasilanie z USB. Sprobuj innego portu USB"
            Info "albo huba z wlasnym zasilaczem."
        }
    }
} catch {
    Warn ("Blad: " + $_.Exception.Message)
    if ($_.Exception.Message -match 'denied|odmow') {
        Info "Port jest zajety przez inny program - najczesciej przez TouchDesignera. Zamknij go i powtorz."
    }
} finally {
    if ($p) { Close-Lidar $p }
}

Write-Host ""
Write-Host "  Port zapisany dla TouchDesignera: $Port" -ForegroundColor Green
Pause-End
