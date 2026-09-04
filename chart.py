"""Top-down plan of the whole aerodrome, drawn from the projected metres.

Drawn 2x and downsampled, so the hairlines stay clean. Everything is in real
metres: a taxiway is drawn 23 m wide because that is how wide it is.
"""
import math, sys
from PIL import Image, ImageDraw, ImageFont
from geo import load
from runways import runways, chain

W, H = 1900, 1258
SS = 2
MARGIN = 58

BG        = (247, 247, 244)
APRON     = (223, 225, 221)
APRON_ED  = (206, 209, 204)
TAXI      = (200, 203, 198)
TAXI_ED   = (176, 180, 174)
RWY       = (74, 76, 80)
RWY_ED    = (52, 54, 58)
TERM      = (126, 150, 178)
TERM_ED   = (86, 108, 134)
STAND     = (222, 132, 44)
INK       = (38, 40, 44)
FAINT     = (128, 132, 136)

F = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def main(out='lfpg_chart.png'):
    ways, nodes, rels = load()
    rwy = runways(ways)
    polys = [w for w in ways + rels if w['kind'] in ('apron', 'terminal', 'hangar')]

    # frame on what actually gets drawn; the aerodrome boundary polygon is much
    # larger than the paved area and would leave the layout floating in space
    drawn = [w for w in ways + rels if w['kind'] != 'aerodrome']
    xs = [p[0] for w in drawn for p in w['pts']]
    ys = [p[1] for w in drawn for p in w['pts']]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    scale = min((W - 2 * MARGIN) / (x1 - x0), (H - 2 * MARGIN) / (y1 - y0)) * SS
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def T(p):
        return (W * SS / 2 + (p[0] - cx) * scale,
                H * SS / 2 - (p[1] - cy) * scale)       # north is up

    im = Image.new('RGB', (W * SS, H * SS), BG)
    d = ImageDraw.Draw(im)
    m = lambda v: max(1, int(round(v * scale)))          # metres -> pixels

    # aprons and hangars first, they sit under everything
    for w in polys:
        if w['kind'] == 'terminal':
            continue
        pts = [T(p) for p in w['pts']]
        if len(pts) > 2:
            d.polygon(pts, fill=APRON, outline=APRON_ED)

    # taxiways
    for w in ways:
        if w['kind'] != 'taxiway':
            continue
        try:
            wid = float(str(w['tags'].get('width', 23)).split()[0])
        except ValueError:
            wid = 23.0
        pts = [T(p) for p in w['pts']]
        if len(pts) > 1:
            d.line(pts, fill=TAXI, width=m(wid), joint='curve')

    # runways: slab, edge, dashed centreline, designators
    for r in rwy:
        pts = [T(p) for p in r['pts']]
        d.line(pts, fill=RWY, width=m(r['width']), joint='curve')
        a, b = T(r['a']), T(r['b'])
        n = int(r['len'] // 60)
        for k in range(n):
            if k % 2:
                continue
            t0, t1 = k / n, min((k + 0.62) / n, 1.0)
            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                    (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)],
                   fill=(238, 238, 234), width=max(1, m(0.9)))

    # terminals on top
    for w in polys:
        if w['kind'] != 'terminal':
            continue
        pts = [T(p) for p in w['pts']]
        if len(pts) > 2:
            d.polygon(pts, fill=TERM, outline=TERM_ED)

    # parking stands
    rad = max(2, m(9))
    for nd in nodes:
        if nd['kind'] not in ('parking_position', 'gate'):
            continue
        x, y = T(nd['xy'])
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=STAND)

    # ---- annotation -----------------------------------------------------
    fb = ImageFont.truetype(FB, 30 * SS)
    fs = ImageFont.truetype(F, 17 * SS)
    fr = ImageFont.truetype(FB, 19 * SS)

    for r in rwy:
        parts = r['ref'].split('/')
        for end, pt, other in ((parts[0], r['a'], r['b']),
                               (parts[-1], r['b'], r['a'])):
            x, y = T(pt)
            ox, oy = T(other)
            dx, dy = x - ox, y - oy
            L = math.hypot(dx, dy) or 1
            x += dx / L * 34 * SS
            y += dy / L * 34 * SS
            bb = d.textbbox((0, 0), end, font=fr)
            d.text((x - (bb[2] - bb[0]) / 2, y - (bb[3] - bb[1]) / 2 - 4 * SS),
                   end, font=fr, fill=INK)

    d.text((MARGIN * SS, (MARGIN - 20) * SS),
           'LFPG  PARIS CHARLES DE GAULLE', font=fb, fill=INK)
    d.text((MARGIN * SS, (MARGIN + 20) * SS),
           'aerodrome layout built from survey data, projected to metres  '
           '•  %d taxiway segments  •  %d stands  •  %d apron / terminal polygons'
           % (sum(1 for w in ways if w['kind'] == 'taxiway'),
              sum(1 for n in nodes if n['kind'] in ('parking_position', 'gate')),
              len(polys)), font=fs, fill=FAINT)

    # scale bar
    bx, by = MARGIN * SS, (H - MARGIN - 4) * SS
    px = 1000 * scale
    d.line([(bx, by), (bx + px, by)], fill=INK, width=3 * SS)
    for t in (0, 1):
        d.line([(bx + px * t, by - 7 * SS), (bx + px * t, by + 7 * SS)],
               fill=INK, width=3 * SS)
    d.text((bx + px + 10 * SS, by - 11 * SS), '1 km', font=fs, fill=INK)

    # north arrow
    nx, ny = (W - MARGIN - 24) * SS, (MARGIN + 40) * SS
    d.polygon([(nx, ny - 26 * SS), (nx - 11 * SS, ny + 14 * SS),
               (nx, ny + 6 * SS), (nx + 11 * SS, ny + 14 * SS)], fill=INK)
    d.text((nx - 7 * SS, ny + 20 * SS), 'N', font=fr, fill=INK)

    im.resize((W, H), Image.LANCZOS).save(out, quality=94)
    print('wrote', out, im.resize((W, H)).size)


if __name__ == '__main__':
    main(*sys.argv[1:])
