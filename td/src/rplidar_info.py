# Script CHOP 'info': liczby do podgladu i do wyrazen w swoim projekcie.
#
#   ok           1 gdy sterownik dziala i skanuje
#   rpm          obroty glowicy na minute
#   revs         licznik obrotow od startu
#   samples      licznik probek od startu
#   errors       odrzucone bajty (kilka na start to norma; rosnace = zly kabel)
#   objects      ile obiektow jest w tej chwili sledzonych
#   points       ile kubelkow ma odbicie
#   background   1 gdy tlo jest nauczone
#   learning     1 w trakcie nauki tla

import numpy as np

CHANS = ('ok', 'rpm', 'revs', 'samples', 'errors', 'objects', 'points',
         'background', 'learning')


def onCook(scriptOp):
    comp = scriptOp.parent()
    drv = mod(comp.op('rplidar_driver')).peek()
    scan = comp.op('scan')
    objs = comp.op('objects')

    points = 0
    if scan is not None and scan.numChans:
        points = int(np.count_nonzero(np.array(scan.chan('dist').vals)))
    objects = 0
    if objs is not None and objs.numChans:
        objects = int(sum(objs.chan('active').vals))

    bg = comp.fetch('background', None)
    vals = {
        'ok': 1.0 if (drv is not None and drv.running
                      and drv.mode != '-') else 0.0,
        'rpm': drv.rpm if drv else 0.0,
        'revs': drv.rev if drv else 0.0,
        'samples': drv.samples if drv else 0.0,
        'errors': drv.errors if drv else 0.0,
        'objects': objects,
        'points': points,
        'background': 1.0 if bg is not None else 0.0,
        'learning': 1.0 if comp.fetch('learn_until', 0.0) > 0.0 else 0.0,
    }
    scriptOp.clear()
    scriptOp.numSamples = 1
    for name in CHANS:
        scriptOp.appendChan(name).vals = [float(vals[name])]
    return
