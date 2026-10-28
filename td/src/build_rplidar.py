# build_rplidar.py - buduje komponent /project1/rplidar i proste demo.
#
# Wykonywany WEWNATRZ TouchDesignera (MCP 'run' albo Textport):
#
#   SRC = r'C:\sciezka\do\paczki\td\src'
#   exec(open(SRC + '/build_rplidar.py').read())
#
# Skrypt wczytuje teksty DAT-ow z plikow .py/.frag lezacych obok siebie, wiec
# zrodlem prawdy sa pliki, a .tox jest tylko ich spakowana kopia. Po kazdej
# zmianie w plikach trzeba uruchomic to ponownie i zapisac projekt.

import os

SRC = SRC            # musi byc ustawione przed exec() - patrz naglowek
PARENT = op('/project1')
VIEWRES = 720


def _read(name):
    with open(os.path.join(SRC, name), 'r', encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------- porzadki

old = PARENT.op('rplidar')
if old:
    try:
        mod(old.op('rplidar_driver')).release()
    except Exception:
        pass
    old.destroy()
for n in ('demo_look', 'demo_fb', 'demo_seed', 'demo_comp', 'demo_view', 'demo_plan',
          'demo_objdata', 'demo_look_pixel', 'demo_look_info',
          'demo_look_compute', 'out1'):
    o = PARENT.op(n)
    if o:
        o.destroy()

L = PARENT.create(baseCOMP, 'rplidar')
L.nodeX, L.nodeY = -400, 200
L.nodeWidth, L.nodeHeight = 180, 110
L.color = (0.18, 0.42, 0.55)
L.comment = ('RPLIDAR A1/A2/A3 na zywo: skan, nauka tla, wykrywanie i '
             'sledzenie obiektow, OSC')


def mk(typ, name, x, y, parent=L):
    o = parent.create(typ, name)
    o.nodeX, o.nodeY = x, y
    # Script CHOP/TOP/DAT tworza sie z wlasnym pustym DAT-em callbackow,
    # ktorego nie uzywamy - nasze teksty maja czytelne nazwy.
    junk = parent.op(name + '_callbacks')
    if junk:
        junk.destroy()
    return o


# ---------------------------------------------------------------- parametry

def P(page, kind, name, label, val=None, lo=None, hi=None):
    p = getattr(page, 'append' + kind)(name, label=label)[0]
    if lo is not None:
        p.normMin, p.normMax = lo, hi
    if val is not None:
        p.default = val
        p.val = val
    return p


pg = L.appendCustomPage('Lidar')
P(pg, 'Toggle', 'Active', 'Aktywny', True)
P(pg, 'Str', 'Port', 'Port COM (auto = szukaj sam)', 'auto')
P(pg, 'Pulse', 'Autodetect', 'Znajdz port')
P(pg, 'Int', 'Pwm', 'Obroty silnika (PWM 0-1023)', 400, 0, 1023)
P(pg, 'Toggle', 'Express', 'Skan express (gestszy)', True)
P(pg, 'Pulse', 'Restart', 'Restart sterownika')

pg = L.appendCustomPage('Tlo i obiekty')
P(pg, 'Pulse', 'Learnbg', 'Naucz tlo (wyjdz z kadru!)')
P(pg, 'Float', 'Learnseconds', 'Czas nauki tla [s]', 3.0, 1.0, 10.0)
P(pg, 'Pulse', 'Clearbg', 'Wyczysc tlo')
P(pg, 'Toggle', 'Usebg', 'Uzywaj tla', True)
P(pg, 'Float', 'Margin', 'Margines tla [mm]', 120.0, 20.0, 500.0)
P(pg, 'Float', 'Rmin', 'Zasieg min [mm]', 150.0, 50.0, 1000.0)
P(pg, 'Float', 'Rmax', 'Zasieg max [mm]', 6000.0, 500.0, 12000.0)
P(pg, 'Int', 'Minbins', 'Min. szerokosc obiektu [kubelki]', 3, 1, 20)
P(pg, 'Int', 'Maxbins', 'Max. szerokosc obiektu (0 = bez limitu)', 80, 0, 256)
P(pg, 'Int', 'Gap', 'Dopuszczalna dziura [kubelki]', 2, 0, 10)
P(pg, 'Float', 'Frontdepth', 'Glebokosc przedniej powierzchni [mm]',
  140.0, 20.0, 600.0)

pg = L.appendCustomPage('Sledzenie')
P(pg, 'Int', 'Slots', 'Liczba slotow', 16, 1, 64)
P(pg, 'Float', 'Maxjump', 'Max. przeskok miedzy klatkami [m]', 0.6, 0.05, 2.0)
P(pg, 'Float', 'Release', 'Zwolnienie numeru po [s]', 0.6, 0.05, 3.0)
P(pg, 'Float', 'Smooth', 'Wygladzanie pozycji', 0.45, 0.0, 0.95)

pg = L.appendCustomPage('Widok')
P(pg, 'Float', 'Range', 'Zasieg widoku [mm]', 4000.0, 500.0, 12000.0)
P(pg, 'Toggle', 'Showbg', 'Pokaz tlo', True)
P(pg, 'Toggle', 'Showobj', 'Pokaz obiekty', True)

pg = L.appendCustomPage('OSC')
P(pg, 'Toggle', 'Oscactive', 'Wysylaj OSC', False)
P(pg, 'Str', 'Oschost', 'Adres odbiorcy', '127.0.0.1')
P(pg, 'Int', 'Oscport', 'Port', 9000, 1, 65535)

# ------------------------------------------------------- moduly i callbacki

MODULES = [
    ('rplidar_driver', 'rplidar_driver.py', 'sterownik: port COM, watek, skan'),
    ('rplidar_logic', 'rplidar_logic.py', 'tlo, bloby, sledzenie - czysta matematyka'),
    ('rplidar_scan', 'rplidar_scan.py', 'callbacki Script CHOP "scan"'),
    ('rplidar_objects', 'rplidar_objects.py', 'callbacki "objects" + nauka tla'),
    ('rplidar_info', 'rplidar_info.py', 'callbacki Script CHOP "info"'),
    ('rplidar_data', 'rplidar_data.py', 'callbacki "cloud" i "objdata"'),
    ('rplidar_view', 'rplidar_view.py', 'callbacki Script TOP "view"'),
    ('rplidar_status', 'rplidar_status.py', 'callbacki Script DAT "status"'),
]
y = 420
for name, fname, note in MODULES:
    d = mk(textDAT, name, -1000, y)
    d.text = _read(fname)
    d.par.language = 'python'
    d.comment = note
    d.color = (0.28, 0.28, 0.34)
    y -= 110

bg = mk(textDAT, 'bg_data', -1000, y)
bg.comment = ('nauczone tlo zapisane jako tekst - dlatego przezywa zapis i '
              'otwarcie projektu')
bg.color = (0.34, 0.3, 0.22)

# ------------------------------------------------------------- lancuch danych

scan = mk(scriptCHOP, 'scan', -620, 300)
scan.par.callbacks = L.op('rplidar_scan')
scan.comment = 'kanal "dist": 512 kubelkow odleglosci w mm, 0 = brak odbicia'

objects = mk(scriptCHOP, 'objects', -320, 300)
objects.par.callbacks = L.op('rplidar_objects')
objects.comment = ('po probce na slot: active, id, x, y, dist, angle, width, '
                   'age, speed')

info = mk(scriptCHOP, 'info', -320, 150)
info.par.callbacks = L.op('rplidar_info')
info.comment = 'diagnostyka: ok, rpm, revs, samples, errors, objects, points'

cloud = mk(scriptTOP, 'cloud', -20, 420)
cloud.par.callbacks = L.op('rplidar_data')
cloud.par.outputresolution = 'custom'
cloud.par.resolutionw, cloud.par.resolutionh = 512, 1
cloud.par.format = 'rgba32float'
cloud.comment = 'R=x[m] G=y[m] B=odleglosc[m] A=odbicie(1)/obiekt(2)'

objdata = mk(scriptTOP, 'objdata', -20, 300)
objdata.par.callbacks = L.op('rplidar_data')
objdata.par.outputresolution = 'custom'
objdata.par.resolutionh = 1
objdata.par.resolutionw.expr = 'parent().par.Slots'
objdata.par.format = 'rgba32float'
objdata.comment = 'R=x[m] G=y[m] B=szerokosc[m] A=1 gdy slot zajety'

view = mk(scriptTOP, 'view', -20, 120)
view.par.callbacks = L.op('rplidar_view')
view.par.outputresolution = 'custom'
view.par.resolutionw, view.par.resolutionh = VIEWRES, VIEWRES
view.comment = ('widok z gory: bialy = skan, niebieski = tlo, czerwony = '
                'obiekty, zielone kolka = sledzone')

status = mk(scriptDAT, 'status', -320, -60)
status.par.callbacks = L.op('rplidar_status')
status.comment = 'TU ZAGLADAJ, gdy nic nie widac'

# ------------------------------------------------------------------- wyjscia

out_view = mk(outTOP, 'out1', 280, 120)
out_view.inputConnectors[0].connect(view)

out_obj = mk(outCHOP, 'out2', 280, 300)
out_obj.inputConnectors[0].connect(objects)

out_info = mk(outCHOP, 'out3', 280, 150)
out_info.inputConnectors[0].connect(info)

osc = mk(oscoutCHOP, 'oscout', 280, 440)
osc.inputConnectors[0].connect(objects)
osc.par.active.expr = 'parent().par.Oscactive'
osc.par.netaddress.expr = 'parent().par.Oschost'
osc.par.port.expr = 'parent().par.Oscport'
osc.par.format = 'transposename'
osc.comment = 'adresy /active /x /y /dist ... z probka na slot'

# ------------------------------------------------------------------- execy

ex = mk(executeDAT, 'exec', -1000, 530)
ex.text = _read('rplidar_exec.py')
ex.par.start = True
ex.par.exit = True
ex.par.framestart = True
ex.par.projectpresave = True
ex.comment = 'wymusza gotowanie co klatke - bez tego dane zamarzaja'
ex.color = (0.5, 0.25, 0.25)

pe = mk(parameterexecuteDAT, 'pars', -780, 530)
pe.text = _read('rplidar_pars.py')
pe.par.op = '..'
pe.par.pars = '*'        # puste pole = ZADEN parametr, nie "wszystkie"
pe.par.builtin = False
pe.par.custom = True
pe.par.valuechange = True
pe.par.onpulse = True
pe.comment = 'reakcje na Restart / Znajdz port / Naucz tlo'
pe.color = (0.5, 0.25, 0.25)

# --------------------------------------------------------------------- demo
#
# UWAGA: polaczen nie da sie poprowadzic przez granice komponentu - przewod
# z /project1/rplidar/objdata do /project1/demo_look po prostu sie nie zrobi,
# i to po cichu. Dlatego Select TOP, ktory siega po operator sciezka.

sel_obj = PARENT.create(selectTOP, 'demo_objdata')
sel_obj.nodeX, sel_obj.nodeY = -120, 40
sel_obj.par.top = 'rplidar/objdata'

sel_plan = PARENT.create(selectTOP, 'demo_plan')
sel_plan.nodeX, sel_plan.nodeY = -120, 180
sel_plan.par.top = 'rplidar/view'

# Feedback TOP potrzebuje DWOCH rzeczy: parametru "Target TOP" (ktorego
# poprzednia klatke oddaje) ORAZ wejscia, od ktorego zaczyna - inaczej zglasza
# "Not enough sources specified". Wejsciem jest czarna klatka.
seed = PARENT.create(constantTOP, 'demo_seed')
seed.nodeX, seed.nodeY = -380, -100
seed.par.outputresolution = 'custom'
seed.par.resolutionw, seed.par.resolutionh = 1280, 720
seed.par.colorr = seed.par.colorg = seed.par.colorb = 0.0
seed.par.alpha = 1.0

fb = PARENT.create(feedbackTOP, 'demo_fb')
fb.nodeX, fb.nodeY = -120, -100
fb.inputConnectors[0].connect(seed)

look = PARENT.create(glslTOP, 'demo_look')
look.nodeX, look.nodeY = 120, -60
look.par.outputresolution = 'custom'
look.par.resolutionw, look.par.resolutionh = 1280, 720
look.par.format = 'rgba16float'
look.par.pixeldat.eval().text = _read('demo.frag')
look.inputConnectors[0].connect(fb)
look.inputConnectors[1].connect(sel_obj)
look.par.vec0name = 'uRange'
look.par.vec0valuex.expr = "op('rplidar').par.Range / 1000.0"
look.par.vec1name = 'uFade'
look.par.vec1valuex = 0.92
look.par.vec2name = 'uGlow'
look.par.vec2valuex = 1.0
look.comment = 'poswiata w miejscach obiektow + smugi z Feedback TOP'
fb.par.top = look

dview = PARENT.create(levelTOP, 'demo_view')
dview.nodeX, dview.nodeY = 120, 180
dview.par.opacity = 0.35
dview.inputConnectors[0].connect(sel_plan)

dcomp = PARENT.create(compositeTOP, 'demo_comp')
dcomp.nodeX, dcomp.nodeY = 380, 20
dcomp.par.operand = 'add'
dcomp.par.outputresolution = 'custom'
dcomp.par.resolutionw, dcomp.par.resolutionh = 1280, 720
dcomp.inputConnectors[0].connect(look)
dcomp.inputConnectors[1].connect(dview)

final = PARENT.create(nullTOP, 'out1')
final.nodeX, final.nodeY = 620, 20
final.inputConnectors[0].connect(dcomp)
final.viewer = True

print('zbudowano', L.path)
print('operatory:', ', '.join(sorted(c.name for c in L.children)))

# ------------------------------------------------------------- notka w projekcie

note = PARENT.op('czytaj_mnie') or PARENT.create(textDAT, 'czytaj_mnie')
note.nodeX, note.nodeY = -400, 420
note.color = (0.45, 0.4, 0.2)
note.text = (
    "RPLIDAR w TouchDesignerze - od czego zaczac\n"
    "\n"
    "1. Wejdz do komponentu 'rplidar' i spojrz na DAT 'status'.\n"
    "   To jedyne miejsce, do ktorego warto zagladac, gdy cos nie dziala.\n"
    "\n"
    "2. Gdy pisze DZIALA - wyjdz z zasiegu czujnika i pulsnij 'Naucz tlo'\n"
    "   (parametry komponentu, strona 'Tlo i obiekty'). Przez 3 sekundy\n"
    "   zapamietuje, jak wyglada puste pomieszczenie. Od tej chwili obiektem\n"
    "   jest tylko to, czego w nim nie bylo - czyli ludzie.\n"
    "\n"
    "3. Co z komponentu wychodzi:\n"
    "     scan     - 512 kubelkow odleglosci w mm\n"
    "     objects  - po probce na obiekt: x, y (metry), dist, angle, width\n"
    "     view     - widok z gory\n"
    "     cloud    - 512 punktow jako tekstura, pod instancing i GLSL\n"
    "     objdata  - pozycje obiektow jako tekstura (uzywa jej demo)\n"
    "\n"
    "4. Demo to demo_seed -> demo_fb -> demo_look (GLSL) + widok z gory -> out1.\n"
    "   Caly shader ma 40 linii i siedzi w DAT 'demo_look_pixel'. Przerob go.\n"
    "\n"
    "Port COM jest na wylacznosc: zanim uruchomisz sprawdz-lidar.bat, odznacz\n"
    "'Active' na komponencie albo zamknij TouchDesignera.\n"
    "\n"
    "Cala reszta: README.md w folderze paczki.\n"
)
