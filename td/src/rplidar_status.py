# Script DAT 'status': stan czujnika po polsku, zeby nie trzeba bylo czytac
# kodu ani Textportu, gdy cos nie dziala.
#
# To pierwsze miejsce, do ktorego zagladamy, gdy "nic nie widac".


def onCook(dat):
    comp = dat.parent()
    drvmod = mod(comp.op('rplidar_driver'))
    drv = drvmod.peek()
    lines = []

    if not comp.par.Active.eval():
        lines.append('WYLACZONY - zaznacz parametr Active na komponencie.')
    elif drv is None:
        err = comp.fetch('error', '')
        lines.append('BRAK POLACZENIA' + (': ' + err if err else ''))
        ports = drvmod.list_ports()
        lines.append('porty COM w systemie: ' +
                     (', '.join(ports) if ports else 'zadnego'))
        lines.append('')
        lines.append('Po kolei:')
        lines.append(' 1. lidar podlaczony do USB i glowica sie kreci?')
        lines.append(' 2. port nie jest zajety przez sprawdz-lidar.bat ani drugi TouchDesigner?')
        lines.append(' 3. uruchom sprawdz-lidar.bat z folderu paczki')
        lines.append(' 4. Port = auto albo wpisz recznie, np. COM10; potem pulsnij Restart')
    else:
        head = 'DZIALA' if drv.mode != '-' else 'LACZY SIE'
        lines.append('%s  port %s  tryb %s' % (head, drv.port, drv.mode))
        lines.append('stan sterownika: %s' % drv.status)
        lines.append('obroty: %.0f rpm   obrotow: %d   probek: %d   bledow: %d'
                     % (drv.rpm, drv.rev, drv.samples, drv.errors))
        if drv.info:
            lines.append('czujnik: %s, firmware %s, hardware %s'
                         % (drv.info.get('name', '?'),
                            drv.info.get('firmware', '?'),
                            drv.info.get('hardware', '?')))
        err = comp.fetch('error', '')
        if err:
            lines.append('ostatni blad: %s' % err)

    bg = comp.fetch('background', None)
    learning = comp.fetch('learn_until', 0.0) > 0.0
    lines.append('')
    if learning:
        lines.append('TLO: ucze sie... wyjdz z kadru!')
    elif bg is None:
        lines.append('TLO: nie nauczone - wszystko w zasiegu jest "obiektem".')
        lines.append('     Wyjdz z kadru i pulsnij "Naucz tlo".')
    else:
        lines.append('TLO: nauczone (%d kubelkow ze sciana)'
                     % int((bg > 0).sum()))

    dat.text = '\n'.join(lines)
    return
