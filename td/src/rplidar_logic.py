"""Tlo, wykrywanie obiektow i sledzenie - czysta matematyka, zero TouchDesignera.

Pomysl jest prosty: najpierw uczymy sie, jak wyglada PUSTE pomieszczenie
(odleglosc do sciany w kazdym kierunku), a potem wszystko, co zwraca blizej
niz to tlo, jest "czyms nowym" - czlowiekiem, dlonia, przesunietym krzeslem.

Wszystkie funkcje operuja na tablicach numpy o dlugosci BINS (domyslnie 512),
indeksowanych katem: kubelek k to kat k * 360 / BINS stopni. Odleglosci
w milimetrach, 0.0 oznacza brak odbicia.
"""

import collections

import numpy as np


# ------------------------------------------------------------------- tlo

def learn_background(frames, pct=80.0):
    """Odleglosc pustego pomieszczenia na kubelek, z paczki obrotow.

    Wysoki percentyl, a nie srednia: gdy ktos przejdzie w trakcie nauki,
    srednia wpiekla by falszywa "sciane" blisko czujnika, a percentyl 80
    takiego przechodnia zignoruje.

    Kubelek, ktory NIGDY nic nie zwrocil, zostaje na 0 - to otwarta przestrzen
    (drzwi, korytarz), w ktorej kazde odbicie jest nowym obiektem.

    Prog "widziany wystarczajaco czesto" jest celowo niski (15% obrotow).
    Przy wysokim progu kazda sciana widziana pod ostrym katem albo ciemna
    powierzchnia, ktora odbija raz na kilka obrotow, ladowala w "otwartej
    przestrzeni" - i caly pokoj swiecil sie potem jako obiekty.
    """
    a = np.stack(frames).astype(np.float32)
    a[a <= 0] = np.nan
    with np.errstate(all="ignore"):
        bg = np.nanpercentile(a, pct, axis=0)
    seen = np.count_nonzero(~np.isnan(a), axis=0)
    bg[~np.isfinite(bg)] = 0.0
    bg[seen < max(2, 0.15 * a.shape[0])] = 0.0
    return bg.astype(np.float32)


def foreground(dist, bg, margin_mm=120.0, margin_rel=0.04,
               rmin=150.0, rmax=6000.0):
    """Maska kubelkow, w ktorych stoi cos, czego nie bylo w pustym pokoju.

    Margines ma czesc stala i czesc proporcjonalna do odleglosci, bo szum
    pomiaru rosnie z dystansem: 12 cm przy scianie i 12 cm + 4% dalej.
    """
    if bg is None:
        return np.zeros(dist.size, bool)
    limit = np.where(bg > 0, bg - (margin_mm + margin_rel * bg), rmax)
    return (dist > rmin) & (dist < rmax) & (dist < limit)


def occupancy(dist, rmin=150.0, rmax=6000.0):
    """Maska "tu cos jest" bez zadnego tla - do zabawy przed nauka tla."""
    return (dist > rmin) & (dist < rmax)


# ----------------------------------------------------------------- obiekty

def _groups(idx, n, gap):
    """Dzieli posortowane indeksy kubelkow na ciagi, swiadome zawiniecia na 0."""
    if idx.size == 0:
        return []
    runs, cur = [], [idx[0]]
    for k in idx[1:]:
        if k - cur[-1] <= gap + 1:
            cur.append(k)
        else:
            runs.append(cur)
            cur = [k]
    runs.append(cur)
    if len(runs) > 1 and (runs[0][0] + n) - runs[-1][-1] <= gap + 1:
        runs[0] = runs[-1] + runs[0]
        runs.pop()
    return runs


def blobs(mask, dist, min_bins=2, gap=2, front_mm=140.0, max_bins=0):
    """Skleja kubelki maski w obiekty. Zwraca liste slownikow.

    Liczy sie tylko PRZEDNIA powierzchnia kazdej grupy: wyciagnieta reka
    zapala wiele kubelkow, ale dlon to ta czesc, ktora jest najblizej
    czujnika. Bez tego srodek obiektu wedrowalby po calym ramieniu.

    Klucze: angle [stopnie], dist [mm], bins, x, y [m], width [m].
    """
    n = mask.size
    out = []
    for run in _groups(np.flatnonzero(mask), n, gap):
        if len(run) < min_bins:
            continue
        if max_bins and len(run) > max_bins:
            continue                      # cala sciana, nie obiekt
        full = np.array(run) % n
        d = dist[full]
        near = d.min()
        front = full[d <= near + front_mm]
        if front.size == 0:
            continue
        fd = dist[front]
        # kat jako srednia wektorowa, zeby grupa przez 0 stopni nie dala 180
        ang = np.radians(front * (360.0 / n))
        cx = float(np.mean(np.sin(ang) * fd))
        cy = float(np.mean(np.cos(ang) * fd))
        cdist = float(np.hypot(cx, cy))
        cang = float(np.degrees(np.arctan2(cx, cy)) % 360.0)
        width = float(np.radians(front.size * (360.0 / n)) * max(cdist, 1.0))
        out.append({"angle": cang, "dist": cdist, "bins": int(front.size),
                    "x": cx / 1000.0, "y": cy / 1000.0,
                    "width": width / 1000.0,
                    "strength": float(front.size) / n})
    out.sort(key=lambda b: b["dist"])
    return out


def polar_to_xy(angle_deg, dist_mm):
    """Kat i odleglosc -> metry w ukladzie czujnika: x w prawo, y do przodu."""
    a = np.radians(angle_deg)
    return np.sin(a) * dist_mm / 1000.0, np.cos(a) * dist_mm / 1000.0


# ---------------------------------------------------------------- sledzenie

class Track:
    __slots__ = ("id", "x", "y", "dist", "angle", "width", "seen", "last",
                 "born", "vx", "vy")

    def __init__(self, tid, b, now):
        self.id = tid
        self.x, self.y = b["x"], b["y"]
        self.dist, self.angle, self.width = b["dist"], b["angle"], b["width"]
        self.vx = self.vy = 0.0
        self.seen = now
        self.last = now
        self.born = now


class Tracker:
    """Nadaje obiektom trwale numery, zeby mialy tozsamosc miedzy klatkami.

    Bez tego lista obiektow zmienia kolejnosc co klatke i nie da sie powiedziec
    "ten sam czlowiek przeszedl stad tam" - a wlasnie o to chodzi w instalacji.

    max_jump  - ile metrow obiekt moze przeskoczyc miedzy klatkami i wciaz byc soba
    release   - po ilu sekundach bez widoku numer zwalnia sie do ponownego uzycia
    smooth    - 0 = bez wygladzania, 0.9 = bardzo leniwe
    """

    def __init__(self, slots=16, max_jump=0.6, release=0.35, smooth=0.45,
                 min_age=0.0):
        self.slots = slots
        self.max_jump = max_jump
        self.release = release
        self.smooth = smooth
        self.min_age = min_age
        self._tracks = collections.OrderedDict()
        self._next = 1
        self.events = collections.deque(maxlen=64)

    def update(self, found, now):
        """`found` to wynik blobs(). Zwraca liste aktywnych Track."""
        tracks = self._tracks
        free = list(found)
        used = set()

        # najpierw dopasuj istniejace numery do najblizszych obiektow
        for tid, tr in list(tracks.items()):
            best, bd = None, self.max_jump
            for i, b in enumerate(free):
                if i in used:
                    continue
                d = ((b["x"] - tr.x) ** 2 + (b["y"] - tr.y) ** 2) ** 0.5
                if d < bd:
                    best, bd = i, d
            if best is None:
                if now - tr.last > self.release:
                    del tracks[tid]
                continue
            b = free[best]
            used.add(best)
            s = self.smooth
            nx = tr.x * s + b["x"] * (1 - s)
            ny = tr.y * s + b["y"] * (1 - s)
            tr.vx, tr.vy = nx - tr.x, ny - tr.y
            tr.x, tr.y = nx, ny
            tr.dist = tr.dist * s + b["dist"] * (1 - s)
            tr.angle = b["angle"]
            tr.width = tr.width * s + b["width"] * (1 - s)
            tr.last = now

        # co zostalo, dostaje nowy numer
        for i, b in enumerate(found):
            if i in used or len(tracks) >= self.slots:
                continue
            tid = self._next
            self._next += 1
            tracks[tid] = Track(tid, b, now)
            self.events.append({"id": tid, "x": b["x"], "y": b["y"],
                                "t": now, "kind": "enter"})

        return [t for t in tracks.values() if now - t.born >= self.min_age]

    def reset(self):
        self._tracks.clear()
        self.events.clear()
