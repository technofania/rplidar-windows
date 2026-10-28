"""RPLIDAR A1/A2/A3 dla TouchDesignera na Windowsie.

Bez pyserial: rozmawia z portem COM przez kernel32 (ctypes), na osobnym watku,
zeby zatkane gotowanie sieci nie gubilo danych skanu.

Skan "express" (0x82, 4000 probek/s) przy silniku zwolnionym do ~450 rpm daje
okolo 0,7 stopnia rozdzielczosci katowej. To wlasnie dlatego dlon na scianie
jest widoczna jako grupa probek, a nie jedna zgubiona kropka. Na fabrycznych
~810 rpm wychodzi 2,9 stopnia - za grubo na cokolwiek poza "ktos tam jest".

Skan trzymany jest jako JEDEN trwaly pierscien BINS kubelkow odleglosci ze
znacznikiem obrotu na kazdym kubelku, a nie jako podwojny bufor przepisywany
co obrot. Dzieki temu nie ma szwu na 0 stopni, a kubelek, ktory przestal
zwracac odbicie, po prostu sie starzeje i gasnie.

Uzycie z TouchDesignera (patrz rplidar_scan.py):
    drv = mod('rplidar_driver').acquire(port='COM10')
    dist = drv.snapshot()      # float32[BINS], milimetry, 0.0 = brak odbicia
"""

import builtins
import ctypes
import ctypes.wintypes as wt
import os
import threading
import time

import numpy as np

BINS = 512            # 0,70 stopnia - dopasowane do skanu express przy ~450 rpm
DEFAULT_PWM = 400     # ~450 rpm na A2; fabrycznie 660 (~810 rpm)
MAX_GAP = 4           # tyle kubelkow dziury interpolujemy
STALE_REVS = 2        # kubelek bez odbicia przez tyle obrotow czyta sie jako pusty

k32 = ctypes.windll.kernel32

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
SETDTR, CLRDTR = 5, 6
PURGE_RXCLEAR, PURGE_TXCLEAR = 0x0008, 0x0004
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
ERROR_ACCESS_DENIED = 5
ERROR_FILE_NOT_FOUND = 2


class DCB(ctypes.Structure):
    _fields_ = [
        ("DCBlength", wt.DWORD), ("BaudRate", wt.DWORD), ("_bf", wt.DWORD),
        ("wReserved", wt.WORD), ("XonLim", wt.WORD), ("XoffLim", wt.WORD),
        ("ByteSize", ctypes.c_byte), ("Parity", ctypes.c_byte),
        ("StopBits", ctypes.c_byte), ("XonChar", ctypes.c_char),
        ("XoffChar", ctypes.c_char), ("ErrorChar", ctypes.c_char),
        ("EofChar", ctypes.c_char), ("EvtChar", ctypes.c_char),
        ("wReserved1", wt.WORD),
    ]


class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ("ReadIntervalTimeout", wt.DWORD),
        ("ReadTotalTimeoutMultiplier", wt.DWORD),
        ("ReadTotalTimeoutConstant", wt.DWORD),
        ("WriteTotalTimeoutMultiplier", wt.DWORD),
        ("WriteTotalTimeoutConstant", wt.DWORD),
    ]


def _checksummed(cmd, payload=b""):
    req = bytes([0xA5, cmd])
    if payload:
        req += bytes([len(payload)]) + payload
        cs = 0
        for x in req:
            cs ^= x
        req += bytes([cs])
    return req


def fill_gaps(d, max_gap=MAX_GAP):
    """Interpoluje krotkie dziury w pierscieniu odleglosci. Zwraca nowa tablice."""
    n = d.size
    idx = np.flatnonzero(d)
    if idx.size < 8:
        return d
    xi = np.concatenate([idx - n, idx, idx + n])
    yi = np.tile(d[idx], 3)
    pos = np.arange(n)
    interp = np.interp(pos, xi, yi)
    j = np.searchsorted(xi, pos, side="left")
    j = np.clip(j, 1, xi.size - 1)
    width = xi[j] - xi[j - 1]
    return np.where((d > 0) | (width <= max_gap + 1), interp, 0.0
                    ).astype(np.float32)


# ------------------------------------------------------------------- porty

def list_ports():
    """Porty COM obecne w tej chwili (nie wpisy-widma w rejestrze)."""
    try:
        import winreg
        out = []
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DEVICEMAP\SERIALCOMM") as k:
            i = 0
            while True:
                try:
                    _, val, _ = winreg.EnumValue(k, i)
                except OSError:
                    break
                out.append(val)
                i += 1
        return sorted(set(out), key=lambda s: (len(s), s))
    except Exception:
        return []


def saved_port():
    """Port zapisany przez INSTALUJ.bat / sprawdz-lidar.bat, albo None."""
    try:
        p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "RPLidarTD",
                         "port.txt")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                v = f.read().strip()
            return v or None
    except Exception:
        pass
    return None


def probe(port, timeout=1.2):
    """Czy na tym porcie odpowiada RPLIDAR? Zwraca slownik info albo None.

    Nie wolno wolac, gdy port trzyma dzialajacy sterownik - port COM jest na
    wylacznosc i proba otwarcia skonczy sie bledem dostepu.
    """
    h = None
    try:
        h = _raw_open(port)
        _raw_write(h, _checksummed(0x25))      # STOP
        time.sleep(0.06)
        k32.PurgeComm(h, PURGE_RXCLEAR | PURGE_TXCLEAR)
        _raw_write(h, _checksummed(0x50))      # GET_INFO
        d, t0 = b"", time.time()
        while len(d) < 27 and time.time() - t0 < timeout:
            d += _raw_read(h, 27 - len(d))
        if len(d) >= 27 and d[:2] == b"\xa5\x5a" and d[2] == 0x14:
            p = d[7:27]
            return {"port": port, "model": p[0],
                    "firmware": "%d.%02d" % (p[2], p[1]), "hardware": p[3],
                    "serial": p[4:20][::-1].hex().upper(),
                    "name": model_name(p[0])}
    except Exception:
        return None
    finally:
        if h:
            try:
                k32.EscapeCommFunction(h, SETDTR)   # silnik stop
                k32.CloseHandle(h)
            except Exception:
                pass
    return None


def model_name(model):
    return {0x12: "RPLIDAR A1", 0x14: "RPLIDAR A1", 0x18: "RPLIDAR A2M8",
            0x28: "RPLIDAR A2M8 / A2", 0x29: "RPLIDAR A2M12",
            0x31: "RPLIDAR A3", 0x61: "RPLIDAR S1",
            }.get(model, "model 0x%02X" % model)


def autodetect(prefer=None):
    """Nazwa portu, na ktorym odpowiada RPLIDAR, albo None.

    Kolejnosc: port podany/zapamietany, potem reszta portow obecnych w systemie.
    Zajety port jest pomijany po cichu - to najczesciej drugi egzemplarz
    TouchDesignera albo otwarta diagnostyka.
    """
    ports = list_ports()
    order = []
    for p in (prefer, saved_port()):
        if p and p in ports and p not in order:
            order.append(p)
    order += [p for p in ports if p not in order]
    for p in order:
        if probe(p):
            return p
    return None


def _raw_open(port):
    name = "\\\\.\\" + port
    h = k32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None,
                        OPEN_EXISTING, 0, None)
    if h in (INVALID_HANDLE_VALUE, 0, -1):
        err = ctypes.GetLastError()
        if err == ERROR_ACCESS_DENIED:
            raise OSError("port %s jest zajety przez inny program "
                          "(drugi TouchDesigner? otwarta diagnostyka?)" % port)
        if err == ERROR_FILE_NOT_FOUND:
            raise OSError("portu %s nie ma w systemie" % port)
        raise OSError("nie moge otworzyc %s (blad %d)" % (port, err))
    h = wt.HANDLE(h)
    k32.SetupComm(h, 262144, 4096)
    dcb = DCB()
    dcb.DCBlength = ctypes.sizeof(DCB)
    if not k32.GetCommState(h, ctypes.byref(dcb)):
        k32.CloseHandle(h)
        raise OSError("GetCommState failed on %s" % port)
    dcb.BaudRate = 115200
    dcb.ByteSize = 8
    dcb.Parity = 0        # NOPARITY
    dcb.StopBits = 0      # ONESTOPBIT
    dcb._bf = 0x0001      # fBinary=1, bez sterowania przeplywem, DTR/RTS off
    if not k32.SetCommState(h, ctypes.byref(dcb)):
        k32.CloseHandle(h)
        raise OSError("SetCommState failed on %s" % port)
    k32.SetCommTimeouts(h, ctypes.byref(COMMTIMEOUTS(10, 0, 60, 0, 200)))
    # Przejsciowka RPLIDAR-a: DTR zdjety trzyma silnik w ruchu.
    k32.EscapeCommFunction(h, CLRDTR)
    k32.PurgeComm(h, PURGE_RXCLEAR | PURGE_TXCLEAR)
    return h


def _raw_write(h, data):
    buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
    n = wt.DWORD(0)
    k32.WriteFile(h, buf, len(data), ctypes.byref(n), None)
    return n.value


def _raw_read(h, n=4096):
    buf = (ctypes.c_char * n)()
    got = wt.DWORD(0)
    if not k32.ReadFile(h, buf, n, ctypes.byref(got), None):
        return b""
    return buf.raw[:got.value]


# ------------------------------------------------------------------ sterownik

class RPLidar:
    def __init__(self, port="COM10", bins=BINS, pwm=DEFAULT_PWM, express=True):
        self.port = port
        self.bins = bins
        self.pwm = pwm
        self.express = express
        self.h = None
        self._thread = None
        self._run = False
        self._lock = threading.Lock()
        self._dist = np.zeros(bins, np.float32)
        self._stamp = np.full(bins, -1e6, np.float32)
        self.rev = 0
        self.samples = 0
        self.errors = 0
        self.status = "idle"
        self.mode = "-"
        self.info = {}
        self.last_rev_time = 0.0
        self.rpm = 0.0

    # ---------------- cykl zycia ----------------

    def start(self):
        """Otwiera port (synchronicznie, zeby blad byl od razu widoczny)
        i rusza watkiem czytajacym."""
        if self.running:
            return self
        self.h = _raw_open(self.port)      # rzuca OSError z czytelnym opisem
        self.status = "otwarty"
        self._run = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="rplidar-" + self.port)
        self._thread.start()
        return self

    def stop(self):
        """Zatrzymuje watek i DOPIERO POTEM zamyka port.

        Kolejnosc ma znaczenie: zamkniecie uchwytu pod dzialajacym watkiem
        zostawia watek zywy w petli czytania, a port - zajety. Tak powstawaly
        "osierocone" sterowniki, po ktorych COM byl zablokowany do restartu
        TouchDesignera.
        """
        self._run = False
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None
        if self.h:                 # watek powinien byl zamknac sam; na wszelki wypadek
            self._close()
        self.status = "zatrzymany"

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def _close(self):
        h, self.h = self.h, None
        if not h:
            return
        try:
            _raw_write(h, _checksummed(0x25))     # STOP
            time.sleep(0.05)
            k32.EscapeCommFunction(h, SETDTR)     # silnik stop
            k32.CloseHandle(h)
        except Exception:
            pass

    def set_motor(self, pwm):
        """0..1023. Wolniejszy silnik = wiecej probek na obrot."""
        self.pwm = int(max(0, min(1023, pwm)))
        if self.h:
            _raw_write(self.h, _checksummed(
                0xF0, bytes([self.pwm & 0xFF, (self.pwm >> 8) & 0xFF])))

    # ---------------- dane ----------------

    def snapshot(self, fill=True):
        """Ostatni pelny obrot jako float32[bins] w mm; 0.0 = brak odbicia."""
        with self._lock:
            d = self._dist.copy()
            stamp = self._stamp.copy()
            rev = self.rev
        d[(rev - stamp) > STALE_REVS] = 0.0
        return fill_gaps(d) if fill else d

    def read_info(self):
        """GET_INFO na dzialajacym porcie. Przerywa skan, wiec wolamy to raz."""
        if not self.h:
            return {}
        _raw_write(self.h, _checksummed(0x25))
        time.sleep(0.06)
        k32.PurgeComm(self.h, PURGE_RXCLEAR)
        _raw_write(self.h, _checksummed(0x50))
        d, t0 = b"", time.time()
        while len(d) < 27 and time.time() - t0 < 1.0:
            d += _raw_read(self.h, 27 - len(d))
        if len(d) >= 27 and d[:2] == b"\xa5\x5a":
            p = d[7:27]
            self.info = {"model": p[0], "firmware": "%d.%02d" % (p[2], p[1]),
                         "hardware": p[3],
                         "serial": p[4:20][::-1].hex().upper(),
                         "name": model_name(p[0])}
        return self.info

    # ---------------- skan ----------------

    def _begin(self, req, want_len, want_type):
        """Wysyla zadanie skanu i sprawdza deskryptor odpowiedzi."""
        _raw_write(self.h, _checksummed(0x25))   # STOP, cokolwiek leci
        time.sleep(0.1)
        k32.PurgeComm(self.h, PURGE_RXCLEAR)
        _raw_write(self.h, req)
        desc, t0 = b"", time.time()
        while len(desc) < 7 and time.time() - t0 < 2.0:
            desc += _raw_read(self.h, 7 - len(desc))
        return (len(desc) == 7 and desc[:2] == b"\xa5\x5a"
                and desc[2] == want_len and desc[6] == want_type)

    def _commit(self, angles, dists):
        """Wrzuca probki jednej kapsuly do pierscienia."""
        if not angles:
            return
        a = np.asarray(angles, np.float32)
        d = np.asarray(dists, np.float32)
        keep = d > 0
        if not keep.any():
            return
        b = (a[keep] * (self.bins / 360.0)).astype(np.int32) % self.bins
        with self._lock:
            self._dist[b] = d[keep]
            self._stamp[b] = self.rev

    def _turned(self):
        now = time.time()
        if self.last_rev_time:
            dt = now - self.last_rev_time
            if dt > 0.001:
                self.rpm = self.rpm * 0.7 + (60.0 / dt) * 0.3
        self.last_rev_time = now
        self.rev += 1

    def _loop(self):
        try:
            self.read_info()
            self.set_motor(self.pwm)
            time.sleep(0.4)
            if self.express and self._begin(
                    _checksummed(0x82, b"\x00\x00\x00\x00\x00"), 0x54, 0x82):
                self.mode = "express"
                self.status = "skanuje"
                self._loop_express()
            elif self._begin(_checksummed(0x20), 0x05, 0x81):
                self.mode = "zwykly"
                self.status = "skanuje"
                self._loop_standard()
            else:
                self.status = "brak odpowiedzi na zadanie skanu (silnik stoi?)"
        except Exception as e:
            self.status = "blad: %r" % (e,)
        finally:
            # Watek zamyka port sam - patrz komentarz w stop().
            self._close()
            if not self.status.startswith("blad"):
                self.status = "zatrzymany"

    def _loop_standard(self):
        buf = b""
        while self._run:
            chunk = _raw_read(self.h, 8192)
            if not chunk:
                continue
            buf += chunk
            angles, dists = [], []
            i, n = 0, len(buf)
            while i + 5 <= n:
                b0, b1 = buf[i], buf[i + 1]
                # bit startu i jego negacja musza sie roznic; bit 0 b1 to bit kontrolny
                if ((b0 & 0x01) == ((b0 >> 1) & 0x01)) or not (b1 & 0x01):
                    i += 1
                    self.errors += 1
                    continue
                quality = b0 >> 2
                angles.append(((b1 >> 1) | (buf[i + 2] << 7)) / 64.0)
                dists.append((buf[i + 3] | (buf[i + 4] << 8)) / 4.0
                             if quality else 0.0)
                if b0 & 0x01:
                    self._turned()
                i += 5
                self.samples += 1
            buf = buf[i:]
            self._commit(angles, dists)

    def _loop_express(self):
        buf = b""
        prev = None  # (start_angle_q6, payload)
        last_q6 = 0
        while self._run:
            chunk = _raw_read(self.h, 8192)
            if not chunk:
                continue
            buf += chunk
            i, n = 0, len(buf)
            while i + 84 <= n:
                if (buf[i] & 0xF0) != 0xA0 or (buf[i + 1] & 0xF0) != 0x50:
                    i += 1
                    self.errors += 1
                    prev = None
                    continue
                pkt = buf[i:i + 84]
                want = (pkt[0] & 0x0F) | ((pkt[1] & 0x0F) << 4)
                got = int(np.bitwise_xor.reduce(
                    np.frombuffer(pkt, np.uint8, 82, 2)))
                if want != got:
                    i += 1
                    self.errors += 1
                    prev = None
                    continue
                i += 84

                cur_q6 = (pkt[2] | (pkt[3] << 8)) & 0x7FFF
                # Bit synchronizacji kapsuly na tym egzemplarzu nie zapala sie nigdy,
                # wiec obrot poznajemy po przewinieciu kata poczatkowego kapsuly.
                if cur_q6 < last_q6:
                    self._turned()
                last_q6 = cur_q6
                if prev is None:
                    prev = (cur_q6, pkt)
                    continue
                prev_q6, prev_pkt = prev
                prev = (cur_q6, pkt)

                # 32 probki rozlozone rowno miedzy katami poczatkowymi dwoch kapsul
                diff_q8 = (cur_q6 << 2) - (prev_q6 << 2)
                if diff_q8 < 0:
                    diff_q8 += 360 << 8
                inc_q16 = diff_q8 << 3
                ang_q16 = (prev_q6 << 2) << 8

                angles, dists = [], []
                for c in range(16):
                    o = 4 + c * 5
                    da1 = prev_pkt[o] | (prev_pkt[o + 1] << 8)
                    da2 = prev_pkt[o + 2] | (prev_pkt[o + 3] << 8)
                    oa = prev_pkt[o + 4]
                    for dist, aoff in (
                            (da1 >> 2, (oa & 0x0F) | ((da1 & 0x03) << 4)),
                            (da2 >> 2, ((oa >> 4) & 0x0F) | ((da2 & 0x03) << 4))):
                        angles.append(((ang_q16 - (aoff << 13)) >> 10) / 64.0)
                        dists.append(float(dist))
                        ang_q16 += inc_q16
                self.samples += 32
                self._commit(angles, dists)
            buf = buf[i:]


# ------------------------------------------------- rejestr na caly proces
#
# Sterownik NIE moze mieszkac tylko w pamieci operatora (op.store). Przeladowanie
# DAT-u, skasowanie komponentu albo wyczyszczenie pamieci operatora zostawia wtedy
# zywy watek z otwartym portem, o ktorym nikt juz nie wie - a port COM jest na
# wylacznosc, wiec nastepna proba konczy sie "port jest zajety" az do restartu
# TouchDesignera. Rejestr siedzi w `builtins`, czyli przezywa kazde przeladowanie
# modulu i kazda zmiane w sieci.

_REG_KEY = "_rplidar_registry_v1"


def _registry():
    r = getattr(builtins, _REG_KEY, None)
    if r is None:
        r = {}
        setattr(builtins, _REG_KEY, r)
    return r


def peek(port=None):
    """Dzialajacy sterownik (dla podanego portu albo jakikolwiek), bez uruchamiania."""
    reg = _registry()
    if port:
        return reg.get(port)
    for d in reg.values():
        if d.running:
            return d
    return None


def acquire(port=None, pwm=DEFAULT_PWM, express=True, restart=False,
            exclusive=True):
    """Zwraca dzialajacy sterownik dla `port`, uruchamiajac go w razie potrzeby.

    port='' albo 'auto' - autodetekcja. `exclusive` zwalnia sterowniki na innych
    portach, zeby dwa komponenty nie trzymaly dwoch lidarow przez przypadek.
    Rzuca OSError z komunikatem po polsku, gdy portu nie da sie otworzyc.
    """
    reg = _registry()
    if not port or str(port).strip().lower() in ("auto", ""):
        have = peek()
        if have is not None and have.running and not restart:
            return have
        port = autodetect()
        if not port:
            raise OSError("nie znalazlem RPLIDAR-a na zadnym porcie COM "
                          "(podlaczony? kreci sie? port nie zajety?)")

    if exclusive:
        for other in [p for p in list(reg) if p != port]:
            release(other)

    drv = reg.get(port)
    if drv is not None and (restart or not drv.running):
        try:
            drv.stop()
        except Exception:
            pass
        reg.pop(port, None)
        drv = None
    if drv is None:
        drv = RPLidar(port=port, pwm=pwm, express=express)
        reg[port] = drv          # wpis PRZED start(), zeby nieudany start tez byl widoczny
        try:
            drv.start()
        except OSError as e:
            # "Port zajety" po wczytaniu innego projektu to prawie zawsze wlasny
            # osierocony watek. Raz sprzatamy i probujemy jeszcze raz.
            if "zajety" in str(e) and reap(port):
                try:
                    drv.start()
                except Exception:
                    reg.pop(port, None)
                    raise
            else:
                reg.pop(port, None)
                raise
        except Exception:
            reg.pop(port, None)
            raise
    return drv


def release(port=None):
    """Zatrzymuje i zapomina sterownik (albo wszystkie, gdy port=None)."""
    reg = _registry()
    for p in ([port] if port else list(reg)):
        drv = reg.pop(p, None)
        if drv is not None:
            try:
                drv.stop()
            except Exception:
                pass


def reap(port=None):
    """Zatrzymuje sterowniki, o ktorych nikt juz nie wie. Zwraca ile ubil.

    Potrzebne, bo wczytanie innego projektu (File > Open) kasuje komponent
    razem z rejestrem, ale NIE zatrzymuje watka czytajacego port - a port COM
    jest na wylacznosc, wiec nowy projekt dostaje "port jest zajety" az do
    restartu TouchDesignera. Tu przechodzimy po obiektach Pythona i zamykamy
    kazdy zywy sterownik, takze ten z poprzedniej wersji tego modulu.
    """
    import gc
    killed = 0
    reg = _registry()
    known = set(id(d) for d in reg.values())
    for o in gc.get_objects():
        if type(o).__name__ != "RPLidar" or id(o) in known:
            continue
        if port and getattr(o, "port", None) != port:
            continue
        if not getattr(o, "h", None) and not getattr(o, "_run", False):
            continue
        try:
            o._run = False
            t = getattr(o, "_thread", None)
            if t is not None and t.is_alive():
                t.join(timeout=1.0)
            h = getattr(o, "h", None)
            if h:
                k32.EscapeCommFunction(h, SETDTR)   # silnik stop
                k32.CloseHandle(h)
                o.h = None
            killed += 1
        except Exception:
            pass
    return killed


def registry_state():
    """Co siedzi w rejestrze - do DAT-u ze statusem."""
    return {p: (d.status, d.running) for p, d in _registry().items()}
