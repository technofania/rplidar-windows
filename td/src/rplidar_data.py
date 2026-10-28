# Dwa Script TOP-y z danymi dla wlasnych shaderow i instancingu.
#
# Ten sam plik obsluguje oba - rozpoznaje sie po nazwie operatora, zeby nie
# trzymac dwoch prawie identycznych DAT-ow.
#
#   'cloud'   512 x 1 RGBA32F   R = x [m], G = y [m], B = odleglosc [m],
#                               A = 1 gdy odbicie / 2 gdy obiekt (nie tlo)
#   'objdata' Slots x 1 RGBA32F R = x [m], G = y [m], B = szerokosc [m],
#                               A = 1 gdy slot zajety
#
# Czemu tekstury, a nie CHOP-y: w GLSL-u siega sie po nie jednym texelFetch,
# bez zadnego kopiowania do uniformow, i dziala to tak samo dla 16 obiektow
# jak dla 512 punktow.

import numpy as np


def onCook(scriptOp):
    if scriptOp.name == 'objdata':
        _objects(scriptOp)
    else:
        _cloud(scriptOp)
    return


def _cloud(scriptOp):
    comp = scriptOp.parent()
    w = int(scriptOp.par.resolutionw)
    img = np.zeros((1, w, 4), np.float32)

    scan = comp.op('scan')
    if scan is not None and scan.numChans:
        d = np.array(scan.chan('dist').vals, np.float32)
        n = min(d.size, w)
        ang = np.radians(np.arange(n) * (360.0 / d.size))
        dd = d[:n]
        img[0, :n, 0] = np.sin(ang) * dd / 1000.0
        img[0, :n, 1] = np.cos(ang) * dd / 1000.0
        img[0, :n, 2] = dd / 1000.0
        fg = comp.fetch('fgmask', None)
        a = (dd > 0).astype(np.float32)
        if fg is not None and fg.size == d.size:
            a = a + fg[:n].astype(np.float32)
        img[0, :n, 3] = a

    scriptOp.copyNumpyArray(img)


def _objects(scriptOp):
    comp = scriptOp.parent()
    w = int(scriptOp.par.resolutionw)
    img = np.zeros((1, w, 4), np.float32)
    for i, (tid, x, y, width) in enumerate(comp.fetch('tracks', None) or []):
        if i >= w:
            break
        img[0, i] = (x, y, width, 1.0)
    scriptOp.copyNumpyArray(img)
