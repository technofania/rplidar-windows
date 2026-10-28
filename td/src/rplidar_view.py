# Script TOP 'view': widok z gory na to, co widzi czujnik.
#
# Bialy   - skan na zywo
# Niebieski - nauczone tlo (puste pomieszczenie)
# Czerwony  - obiekty (to, czego w pustym pomieszczeniu nie bylo)
# Zielone kolka - obiekty po sledzeniu, z numerem slotu
# Znaczniki - 0 stopni czerwony (przod), 90 zielony, 180 niebieski, 270 zolty
#
# UWAGA: copyNumpyArray przykuwa Script TOP do rozmiaru tablicy, ktora dostal
# pierwszy raz. Rozmiar bierzemy z par.resolutionw/h, NIGDY z scriptOp.width -
# inaczej TOP zablokuje sie na domyslnych 128x128 przy pierwszym ugotowaniu.

import numpy as np


def onCook(scriptOp):
    comp = scriptOp.parent()
    w = int(scriptOp.par.resolutionw)
    h = int(scriptOp.par.resolutionh)
    res = min(w, h)
    rng = max(100.0, float(comp.par.Range))

    img = np.zeros((h, w, 4), np.float32)
    img[:, :, 3] = 1.0
    cx, cy = w // 2, h // 2
    s = (res * 0.46) / rng

    # pierscienie co 500 mm
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - cx, yy - cy) / s
    ring = np.abs((r % 500.0) - 250.0) > 247.0
    img[:, :, 0] += ring * 0.10
    img[:, :, 1] += ring * 0.12
    img[:, :, 2] += ring * 0.16

    scan = comp.op('scan')
    if scan is None or scan.numChans == 0:
        scriptOp.copyNumpyArray(img)
        return

    d = np.array(scan.chan('dist').vals, np.float32)
    n = d.size
    ang = np.radians(np.arange(n) * (360.0 / n))
    # wiersz 0 to DOL obrazu w TD, wiec zeby 0 stopni bylo u gory, rosnie sie w plus
    px = cx + np.sin(ang) * d * s
    py = cy + np.cos(ang) * d * s

    bg = comp.fetch('background', None)
    if bg is not None and bg.size == n and comp.par.Showbg.eval():
        ok = bg > 0
        _plot(img, cx + np.sin(ang[ok]) * bg[ok] * s,
              cy + np.cos(ang[ok]) * bg[ok] * s, (0.10, 0.35, 0.75), 0)

    fg = comp.fetch('fgmask', None)
    if fg is None or fg.size != n:
        fg = np.zeros(n, bool)
    live = d > 0
    _plot(img, px[live & ~fg], py[live & ~fg], (0.85, 0.88, 0.95), 1)
    _plot(img, px[live & fg], py[live & fg], (1.0, 0.18, 0.12), 2)

    if comp.par.Showobj.eval():
        for tid, x, y, width in (comp.fetch('tracks', None) or []):
            _circle(img, cx + x * 1000.0 * s, cy + y * 1000.0 * s,
                    max(4.0, width * 1000.0 * s * 0.5), (0.2, 1.0, 0.4))

    # znaczniki kierunkow
    for deg, rgb in ((0, (1, 0.2, 0.2)), (90, (0.2, 1, 0.2)),
                     (180, (0.3, 0.5, 1)), (270, (1, 0.9, 0.2))):
        a = np.radians(deg)
        t = np.linspace(0.80, 0.98, 24) * (res * 0.46)
        _plot(img, cx + np.sin(a) * t, cy + np.cos(a) * t, rgb, 1)

    img[cy - 2:cy + 3, cx - 2:cx + 3, :3] = 1.0      # czujnik
    scriptOp.copyNumpyArray(np.clip(img, 0, 1))
    return


def _plot(img, xs, ys, rgb, size=1):
    h, w = img.shape[:2]
    ok = (xs >= size) & (xs < w - size) & (ys >= size) & (ys < h - size)
    xs, ys = xs[ok].astype(np.int32), ys[ok].astype(np.int32)
    if xs.size == 0:
        return
    for dx in range(-size, size + 1):
        for dy in range(-size, size + 1):
            img[ys + dy, xs + dx, 0] = rgb[0]
            img[ys + dy, xs + dx, 1] = rgb[1]
            img[ys + dy, xs + dx, 2] = rgb[2]


def _circle(img, cx, cy, rad, rgb, width=1.6):
    h, w = img.shape[:2]
    rad = float(min(rad, max(w, h)))
    x0, x1 = int(max(0, cx - rad - 2)), int(min(w, cx + rad + 3))
    y0, y1 = int(max(0, cy - rad - 2)), int(min(h, cy + rad + 3))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.abs(np.hypot(xx - cx, yy - cy) - rad)
    m = d < width
    img[y0:y1, x0:x1, 0][m] = rgb[0]
    img[y0:y1, x0:x1, 1][m] = rgb[1]
    img[y0:y1, x0:x1, 2][m] = rgb[2]
