# Script CHOP 'scan': jeden kanal 'dist' z BINS probkami odleglosci w mm.
#
# Zero logiki poza "podaj ostatni obrot". Sterownik kreci sie na wlasnym watku
# i tutaj tylko przepisujemy jego ostatni stan.
#
# WAZNE: Script CHOP bez wejscia NIGDY nie jest oznaczany jako brudny, wiec
# sam z siebie ugotuje sie raz i do konca zycia projektu bedzie podawal ten sam,
# zamrozony skan. Gotowanie wymusza Execute DAT 'exec' co klatke. Jesli kiedys
# zobaczysz skan, ktory sie nie zmienia, a lidar dziala - sprawdz najpierw to.

import numpy as np

BINS = 512


def onCook(scriptOp):
    comp = scriptOp.parent()
    drv = _driver(comp)

    if drv is None or not drv.running:
        scriptOp.clear()
        scriptOp.numSamples = BINS
        scriptOp.appendChan('dist').vals = np.zeros(BINS, np.float32)
        return

    d = drv.snapshot()
    scriptOp.clear()
    scriptOp.numSamples = d.size
    scriptOp.appendChan('dist').vals = d.astype(np.float32)
    return


RETRY_SECONDS = 2.0


def _driver(comp):
    """Dzialajacy sterownik albo None.

    Blad zapisujemy w pamieci komponentu, zeby DAT 'status' mial co pokazac -
    wyjatek w onCook tylko zaswiecilby operator na czerwono bez wyjasnienia.

    Ponowna proba nie czesciej niz raz na RETRY_SECONDS: przy wyjetym USB
    otwieranie portu co klatke to 60 wywolan CreateFileW na sekunde, a kazde
    z nich potrafi zajac kilka milisekund i zjesc klatke.
    """
    drvmod = mod(comp.op('rplidar_driver'))
    if not comp.par.Active.eval():
        drvmod.release()
        comp.store('error', '')
        return None
    drv = drvmod.peek()
    if drv is not None and drv.running:
        return drv

    now = absTime.seconds
    if now - comp.fetch('last_try', -99.0) < RETRY_SECONDS:
        return None
    comp.store('last_try', now)
    try:
        drv = drvmod.acquire(port=comp.par.Port.eval(),
                             pwm=int(comp.par.Pwm),
                             express=bool(comp.par.Express))
        comp.store('error', '')
        return drv
    except Exception as e:
        comp.store('error', str(e))
        return None
