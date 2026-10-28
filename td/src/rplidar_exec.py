# Execute DAT 'exec': cykl zycia komponentu.
#
# Trzy rzeczy, ktore musza byc w jednym miejscu, bo inaczej projekt wyglada na
# zepsuty bez zadnego komunikatu o bledzie:
#
# 1. Script CHOP/TOP BEZ WEJSCIA nigdy nie jest oznaczany jako brudny. Ugotuje
#    sie raz i potem do konca zycia projektu podaje ten sam wynik. Trzeba je
#    gotowac na piechote, co klatke, w kolejnosci od zrodla. Objaw jest podly:
#    obraz plynie (shadery maja czas w uniformach), a dane stoja.
# 2. Przy zapisie projektu TouchDesigner marynuje (pickle) pamiec operatora.
#    Sterownik to uchwyt Win32 w ctypes, a Tracker to klasa z DAT-u - ani
#    jedno, ani drugie sie nie marynuje, a JEDEN zly klucz wywala CALA pamiec
#    operatora: projekt zapisuje sie "with errors" i nie zostaje z niej nic.
# 3. Port COM jest na wylacznosc. Bez zamkniecia przy wyjsciu zostaje zajety.
#
# Reakcje na parametry (Restart, Naucz tlo, ...) siedza w 'pars' - to
# Parameter Execute DAT, bo zwykly Execute DAT nie dostaje onPulse.

ORDER = ('scan', 'objects', 'info', 'cloud', 'objdata', 'view', 'status')


def onStart():
    comp = me.parent()
    # Jesli ktos wczytal ten projekt NA poprzednim, po tamtym mogl zostac zywy
    # watek z otwartym portem COM. Sprzatamy, zanim sprobujemy go otworzyc.
    try:
        mod(comp.op('rplidar_driver')).reap()
    except Exception:
        pass
    mod(comp.op('rplidar_objects')).load_background(comp)
    comp.store('error', '')
    return


def onFrameStart(frame):
    comp = me.parent()
    if not comp.par.Active.eval():
        # Wylaczony komponent nie musi nic gotowac - poza DAT-em ze statusem,
        # zeby bylo widac, ze jest wylaczony, a nie zepsuty.
        s = comp.op('status')
        if s is not None:
            s.cook(force=True)
        return
    for name in ORDER:
        o = comp.op(name)
        if o is not None:
            o.cook(force=True)
    return


def onProjectPreSave():
    comp = me.parent()
    for key in list(comp.storage.keys()):
        comp.storeStartupValue(key, None)
    return


def onExit():
    mod(me.parent().op('rplidar_driver')).release()
    return
