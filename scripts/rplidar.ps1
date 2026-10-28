# rplidar.ps1 - rozmowa z RPLIDAR-em po COM-ie, czystym PowerShellem.
# Bez Pythona, bez pyserial - zeby diagnostyka dzialala na swiezym Windowsie,
# jeszcze przed instalacja czegokolwiek.
#
# Protokol: kazde zadanie to 0xA5 <komenda> [dlugosc payloadu][payload][suma XOR].
# Odpowiedz zaczyna sie 7-bajtowym deskryptorem: A5 5A <30 bitow dlugosci +
# 2 bity trybu> <typ>.

Set-StrictMode -Off

$script:CMD_STOP       = 0x25
$script:CMD_RESET      = 0x40
$script:CMD_SCAN       = 0x20
$script:CMD_GET_INFO   = 0x50
$script:CMD_GET_HEALTH = 0x52
$script:CMD_MOTOR_PWM  = 0xF0

function Open-Lidar([string]$Port, [int]$Baud = 115200) {
    $p = New-Object System.IO.Ports.SerialPort $Port, $Baud, 'None', 8, 'One'
    $p.ReadTimeout = 500
    $p.WriteTimeout = 500
    $p.ReadBufferSize = 262144
    # Przejsciowka RPLIDAR-a sterowuje silnikiem linia DTR: DTR=0 -> silnik kreci.
    $p.DtrEnable = $false
    $p.RtsEnable = $false
    $p.Open()
    Start-Sleep -Milliseconds 50
    $p.DiscardInBuffer()
    return $p
}

function Close-Lidar($p) {
    if (-not $p) { return }
    try {
        Send-LidarCmd $p $script:CMD_STOP
        Start-Sleep -Milliseconds 60
        $p.DtrEnable = $true      # silnik stop, zeby nie krecil sie po zamknieciu okna
        Start-Sleep -Milliseconds 30
    } catch {}
    try { $p.Close() } catch {}
    try { $p.Dispose() } catch {}
}

function Send-LidarCmd($p, [byte]$Cmd, [byte[]]$Payload = $null) {
    if ($Payload -and $Payload.Length -gt 0) {
        $req = @([byte]0xA5, $Cmd, [byte]$Payload.Length) + $Payload
        $cs = 0
        foreach ($b in $req) { $cs = $cs -bxor $b }
        $req += [byte]$cs
    } else {
        $req = @([byte]0xA5, $Cmd)
    }
    $bytes = [byte[]]$req
    $p.Write($bytes, 0, $bytes.Length)
}

function Read-LidarExact($p, [int]$Count, [int]$TimeoutMs = 2000) {
    $buf = New-Object byte[] $Count
    $got = 0
    $t0 = Get-Date
    while ($got -lt $Count -and ((Get-Date) - $t0).TotalMilliseconds -lt $TimeoutMs) {
        try { $got += $p.Read($buf, $got, $Count - $got) } catch { }
    }
    if ($got -lt $Count) { return $null }
    return $buf
}

# Czyta deskryptor i sprawdza, czy zgadza sie z oczekiwanym typem/dlugoscia.
function Read-LidarDescriptor($p, [int]$WantLen, [int]$WantType, [int]$TimeoutMs = 2000) {
    $d = Read-LidarExact $p 7 $TimeoutMs
    if (-not $d) { return $false }
    return ($d[0] -eq 0xA5 -and $d[1] -eq 0x5A -and $d[2] -eq $WantLen -and $d[6] -eq $WantType)
}

function Set-LidarMotor($p, [int]$Pwm) {
    if ($Pwm -lt 0) { $Pwm = 0 }
    if ($Pwm -gt 1023) { $Pwm = 1023 }
    Send-LidarCmd $p $script:CMD_MOTOR_PWM ([byte[]]@(($Pwm -band 0xFF), (($Pwm -shr 8) -band 0xFF)))
}

function Stop-LidarScan($p) {
    Send-LidarCmd $p $script:CMD_STOP
    Start-Sleep -Milliseconds 100
    $p.DiscardInBuffer()
}

function Get-LidarInfo($p) {
    Stop-LidarScan $p
    Send-LidarCmd $p $script:CMD_GET_INFO
    if (-not (Read-LidarDescriptor $p 0x14 0x04)) { return $null }
    $pl = Read-LidarExact $p 20
    if (-not $pl) { return $null }
    $sn = @($pl[4..19] | ForEach-Object { $_.ToString('X2') })
    [array]::Reverse($sn)
    return [pscustomobject]@{
        Model    = $pl[0]
        Firmware = ('{0}.{1:D2}' -f $pl[2], $pl[1])
        Hardware = $pl[3]
        Serial   = ($sn -join '')
        Name     = (Get-LidarModelName $pl[0])
    }
}

# Bajt modelu -> nazwa handlowa. Lista niepelna; nieznany model nie jest bledem.
function Get-LidarModelName([int]$Model) {
    switch ($Model) {
        18 { 'RPLIDAR A1' }        # 0x12
        20 { 'RPLIDAR A1' }        # 0x14
        24 { 'RPLIDAR A2M8' }      # 0x18
        40 { 'RPLIDAR A2M8 / A2' } # 0x28
        41 { 'RPLIDAR A2M12' }     # 0x29
        49 { 'RPLIDAR A3' }        # 0x31
        97 { 'RPLIDAR S1' }        # 0x61
        default { "model 0x{0:X2} (nieznany, to nie problem)" -f $Model }
    }
}

function Get-LidarHealth($p) {
    Stop-LidarScan $p
    Send-LidarCmd $p $script:CMD_GET_HEALTH
    if (-not (Read-LidarDescriptor $p 0x03 0x06)) { return $null }
    $pl = Read-LidarExact $p 3
    if (-not $pl) { return $null }
    $txt = switch ($pl[0]) {
        0 { 'dobry' }
        1 { 'ostrzezenie' }
        2 { 'BLAD - potrzebny reset' }
        default { "nieznany ($($pl[0]))" }
    }
    return [pscustomobject]@{ Status = $pl[0]; Text = $txt; Error = ($pl[1] + $pl[2] * 256) }
}

# Zwykly skan (0x20) przez $Seconds sekund. Zwraca statystyki albo $null.
function Measure-LidarScan($p, [double]$Seconds = 4.0, [int]$Bins = 360) {
    Stop-LidarScan $p
    Send-LidarCmd $p $script:CMD_SCAN
    if (-not (Read-LidarDescriptor $p 0x05 0x81)) { return $null }

    $hit = New-Object bool[] $Bins
    $samples = 0; $valid = 0; $revs = 0; $bad = 0
    $dmin = [double]::MaxValue; $dmax = 0.0
    # Jeden bufor na cale pomiary: ogon (do 4 bajtow niedokonczonej probki) laduje
    # na jego poczatku, nowe dane doczytuja sie za nim. Bez tego kazde czytanie
    # alokowalo nowa tablice i lidar wyprzedzal parser.
    $buf = New-Object byte[] 65536
    $tailLen = 0
    $t0 = Get-Date
    $firstRev = $null; $lastRev = $null

    while (((Get-Date) - $t0).TotalSeconds -lt $Seconds) {
        $n = 0
        try { $n = $p.Read($buf, $tailLen, $buf.Length - $tailLen) } catch { continue }
        if ($n -le 0) { continue }

        $i = 0
        $len = $tailLen + $n
        while ($i + 5 -le $len) {
            $b0 = $buf[$i]; $b1 = $buf[$i + 1]
            # bit startu i jego negacja musza sie roznic; bit 0 drugiego bajtu to bit kontrolny
            if ((($b0 -band 1) -eq (($b0 -shr 1) -band 1)) -or (($b1 -band 1) -eq 0)) {
                $i++; $bad++
                continue
            }
            # UWAGA: w PowerShellu bitowe -bor rzutuje prawy operand na typ lewego,
            # a tu po lewej stoi [byte]. Bez [int] gorny bajt odleglosci i kata ginie.
            $q = [int]$b0 -shr 2
            $ang = ((([int]$b1 -shr 1) -bor ([int]$buf[$i + 2] -shl 7)) / 64.0)
            $d = (([int]$buf[$i + 3] -bor ([int]$buf[$i + 4] -shl 8)) / 4.0)
            if (($b0 -band 1) -ne 0) {
                $revs++
                if ($null -eq $firstRev) { $firstRev = Get-Date }
                $lastRev = Get-Date
            }
            $samples++
            if ($q -gt 0 -and $d -gt 0) {
                $valid++
                $k = [int]($ang * $Bins / 360.0) % $Bins
                if ($k -ge 0 -and $k -lt $Bins) { $hit[$k] = $true }
                if ($d -lt $dmin) { $dmin = $d }
                if ($d -gt $dmax) { $dmax = $d }
            }
            $i += 5
        }
        $tailLen = $len - $i
        if ($tailLen -gt 0) { [Array]::Copy($buf, $i, $buf, 0, $tailLen) }
    }
    Stop-LidarScan $p

    $elapsed = ((Get-Date) - $t0).TotalSeconds
    $rpm = 0.0
    if ($firstRev -and $lastRev -and $revs -gt 2) {
        $span = ($lastRev - $firstRev).TotalSeconds
        if ($span -gt 0.1) { $rpm = ($revs - 1) * 60.0 / $span }
    }
    if ($dmin -eq [double]::MaxValue) { $dmin = 0.0 }
    return [pscustomobject]@{
        Samples   = $samples
        Valid     = $valid
        Revs      = $revs
        Bad       = $bad
        Rpm       = [math]::Round($rpm, 1)
        PerSecond = [int]($samples / [math]::Max(0.1, $elapsed))
        Coverage  = [int](100.0 * (@($hit | Where-Object { $_ }).Count) / $Bins)
        MinMm     = [int]$dmin
        MaxMm     = [int]$dmax
        Seconds   = [math]::Round($elapsed, 1)
    }
}

# Czy na tym porcie siedzi RPLIDAR? Uzywane do autodetekcji - musi byc szybkie
# i nie moze sie wywalic na porcie zajetym przez inny program.
function Test-LidarPort([string]$Port) {
    $p = $null
    try {
        $p = Open-Lidar $Port
        $info = Get-LidarInfo $p
        if ($info) { return $info }
    } catch {
        return $null
    } finally {
        if ($p) { Close-Lidar $p }
    }
    return $null
}
