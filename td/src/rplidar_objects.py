# Script CHOP 'objects': po jednej probce na slot, kanaly opisujace obiekty.
#
# Kanaly (slot = probka 0..Slots-1):
#   active  1 gdy slot zajety
#   id      trwaly numer obiektu (rosnie, nie wraca)
#   x, y    pozycja w metrach w ukladzie czujnika: x w prawo, y do przodu
#   dist    odleglosc w mm
#   angle   kat w stopniach, 0 = przod czujnika, rosnie w prawo
#   width   szerokosc obiektu w metrach
#   age     ile sekund obiekt jest widziany
#   speed   metry na klatke (dlugosc wektora ruchu)
#
# Tu tez dzieje sie nauka tla, bo wymaga zbierania kolejnych obrotow w czasie.

import numpy as np

CHANS = ('active', 'id', 'x', 'y', 'dist', 'angle', 'width', 'age', 'speed')


def onCook(scriptOp):
    comp = scriptOp.parent()
    logic = mod(comp.op('rplidar_logic'))
    scan = comp.op('scan')

    slots = max(1, int(comp.par.Slots))
    out = np.zeros((len(CHANS), slots), np.float32)

    if scan is None or scan.numChans == 0:
        _emit(scriptOp, out, slots)
        return

    dist = np.array(scan.chan('dist').vals, np.float32)
    now = absTime.seconds

    _learn(comp, logic, dist, now)

    bg = comp.fetch('background', None)
    if comp.par.Usebg.eval() and bg is not None and bg.size == dist.size:
        mask = logic.foreground(dist, bg,
                                margin_mm=float(comp.par.Margin),
                                rmin=float(comp.par.Rmin),
                                rmax=float(comp.par.Rmax))
    else:
        # Bez nauczonego tla pokazujemy wszystko, co jest w zasiegu. Dla
        # instalacji to bezuzyteczne (sciany tez sa "obiektem"), ale student
        # od razu widzi, ze czujnik dziala, zamiast patrzec w czarny ekran.
        mask = logic.occupancy(dist, rmin=float(comp.par.Rmin),
                               rmax=float(comp.par.Rmax))
    comp.store('fgmask', mask)

    found = logic.blobs(mask, dist,
                        min_bins=int(comp.par.Minbins),
                        gap=int(comp.par.Gap),
                        front_mm=float(comp.par.Frontdepth),
                        max_bins=int(comp.par.Maxbins))

    tracker = _tracker(comp, logic, slots)
    tracks = tracker.update(found, now)
    comp.store('tracks', [(t.id, t.x, t.y, t.width) for t in tracks])

    for i, t in enumerate(tracks[:slots]):
        out[0, i] = 1.0
        out[1, i] = t.id
        out[2, i] = t.x
        out[3, i] = t.y
        out[4, i] = t.dist
        out[5, i] = t.angle
        out[6, i] = t.width
        out[7, i] = now - t.born
        out[8, i] = (t.vx ** 2 + t.vy ** 2) ** 0.5

    _emit(scriptOp, out, slots)
    return


def _emit(scriptOp, out, slots):
    scriptOp.clear()
    scriptOp.numSamples = slots
    for name, row in zip(CHANS, out):
        scriptOp.appendChan(name).vals = row
    return


def _tracker(comp, logic, slots):
    """Tracker przezywa klatki w pamieci komponentu. Parametry, ktore mozna
    zmieniac na zywo, przepisujemy przy kazdym cooku - taniej niz budowac
    nowy obiekt i gubic numery przy kazdym ruchu suwaka."""
    tr = comp.fetch('tracker', None)
    if tr is None or tr.slots != slots:
        tr = logic.Tracker(slots=slots)
        comp.store('tracker', tr)
    tr.max_jump = float(comp.par.Maxjump)
    tr.release = float(comp.par.Release)
    tr.smooth = float(comp.par.Smooth)
    return tr


def _learn(comp, logic, dist, now):
    """Zbiera obroty, dopoki trwa nauka, i na koniec liczy tlo.

    Tlo trafia takze do DAT-u 'bg_data', wiec przezywa zapis i otwarcie
    projektu. Jesli pokoj sie zmienil albo czujnik zostal przesuniety -
    trzeba nauczyc od nowa, zapisane tlo nie wie o przeprowadzce.
    """
    until = comp.fetch('learn_until', 0.0)
    if until <= 0.0:
        return
    frames = comp.fetch('learn_frames', None)
    if frames is None:
        frames = []
        comp.store('learn_frames', frames)
    if dist.any():
        frames.append(dist.copy())
    if now < until:
        return

    comp.store('learn_until', 0.0)
    comp.store('learn_frames', None)
    if len(frames) < 5:
        comp.store('error', 'nauka tla: za malo obrotow (%d) - czujnik nie '
                            'nadaje?' % len(frames))
        return
    bg = logic.learn_background(frames)
    comp.store('background', bg)
    save_background(comp, bg)
    comp.store('error', '')


# ----------------------------------------------- wywolywane z parametrow

def learn_start(comp):
    comp.store('learn_frames', [])
    comp.store('learn_until', absTime.seconds + float(comp.par.Learnseconds))
    comp.store('error', '')


def clear_background(comp):
    comp.store('background', None)
    comp.store('learn_until', 0.0)
    comp.store('learn_frames', None)
    d = comp.op('bg_data')
    if d is not None:
        d.text = ''
    tr = comp.fetch('tracker', None)
    if tr is not None:
        tr.reset()


def save_background(comp, bg):
    d = comp.op('bg_data')
    if d is not None:
        d.text = ','.join('%.1f' % v for v in bg)


def load_background(comp):
    """Wczytuje tlo z DAT-u (wolane przy starcie projektu)."""
    d = comp.op('bg_data')
    if d is None or not d.text.strip():
        return
    try:
        bg = np.array([float(x) for x in d.text.split(',')], np.float32)
        if bg.size:
            comp.store('background', bg)
    except Exception as e:
        comp.store('error', 'nie moge wczytac zapisanego tla: %s' % e)
