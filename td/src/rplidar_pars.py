# Parameter Execute DAT 'pars': reakcje na parametry komponentu.
#
# Zwykly Execute DAT nie dostaje onPulse ani onValueChange - dlatego to osobny
# operator. Jego parametr "OP" wskazuje na komponent rplidar.


def onPulse(par):
    comp = par.owner
    drvmod = mod(comp.op('rplidar_driver'))

    if par.name == 'Restart':
        try:
            drvmod.acquire(port=comp.par.Port.eval(), pwm=int(comp.par.Pwm),
                           express=bool(comp.par.Express), restart=True)
            comp.store('error', '')
        except Exception as e:
            comp.store('error', str(e))

    elif par.name == 'Autodetect':
        drvmod.release()                 # port musi byc wolny, zeby go przeszukac
        found = drvmod.autodetect()
        if found:
            comp.par.Port = found
            comp.store('error', '')
        else:
            comp.store('error', 'autodetekcja: zaden port nie odpowiedzial '
                                'jak RPLIDAR')

    elif par.name == 'Learnbg':
        mod(comp.op('rplidar_objects')).learn_start(comp)

    elif par.name == 'Clearbg':
        mod(comp.op('rplidar_objects')).clear_background(comp)
    return


def onValueChange(par, prev):
    comp = par.owner
    drvmod = mod(comp.op('rplidar_driver'))

    if par.name in ('Port', 'Express'):
        # Zmiana portu albo trybu wymaga ponownego otwarcia. Zwalniamy, a
        # 'scan' podniesie sterownik przy nastepnym gotowaniu.
        drvmod.release()
    elif par.name == 'Pwm':
        drv = drvmod.peek()
        if drv is not None:
            drv.set_motor(int(par))
    elif par.name == 'Active' and not par.eval():
        drvmod.release()
    return
