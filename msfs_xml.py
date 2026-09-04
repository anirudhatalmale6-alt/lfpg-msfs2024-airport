"""Emit the MSFS airport definition (bglcomp XML) from the projected layout.

This is the file the SDK's fspackagetool compiles into the aerodrome the sim
actually loads. Written on Linux; NOT compiled or validated here, because the
compiler is Windows-only. Treat every count it prints as "what was written",
not "what the sim accepted".
"""
import math
from xml.sax.saxutils import escape
from geo import load, ARP_LAT, ARP_LON, R
from runways import runways

ELEV_M = 119.0                       # from the aerodrome's own ele tag
MAGVAR = 1.4                         # set this from the current AIP before release

SURFACE = {'asphalt': 'ASPHALT', 'concrete': 'CONCRETE', 'paved': 'ASPHALT',
           'grass': 'GRASS', 'gravel': 'GRAVEL'}


def to_ll(x, y):
    lat = ARP_LAT + math.degrees(y / R)
    lon = ARP_LON + math.degrees(x / (R * math.cos(math.radians(ARP_LAT))))
    return lat, lon


def surf(tags):
    return SURFACE.get(str(tags.get('surface', '')).lower(), 'ASPHALT')


def bearing(a, b):
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360


def main(out='LFPG.xml'):
    ways, nodes, rels = load()
    rwy = runways(ways)
    L = []
    A = L.append

    A('<?xml version="1.0" encoding="UTF-8"?>')
    A('<FSData version="9.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
      ' xsi:noNamespaceSchemaLocation="bglcomp.xsd">')
    A('  <Airport ident="LFPG" region="LF" country="France" city="Paris"'
      ' name="%s" lat="%.9f" lon="%.9f" alt="%.1fM" magvar="%.1f"'
      ' trafficScalar="1.0" airportTestRadius="9000.0M" applyFlatten="FALSE">'
      % (escape('Charles de Gaulle International Airport'),
         ARP_LAT, ARP_LON, ELEV_M, MAGVAR))

    # ---- runways --------------------------------------------------------
    for r in rwy:
        prim = r['ref'].split('/')[0]
        num, desig = prim[:2], prim[2:]
        want = int(num) * 10
        bAB, bBA = bearing(r['a'], r['b']), bearing(r['b'], r['a'])
        dev = lambda b: abs((b - want + 180) % 360 - 180)
        if dev(bAB) <= dev(bBA):
            thr, hdg = r['a'], bAB
        else:
            thr, hdg = r['b'], bBA
        cx = (r['a'][0] + r['b'][0]) / 2
        cy = (r['a'][1] + r['b'][1]) / 2
        lat, lon = to_ll(cx, cy)
        A('    <Runway lat="%.9f" lon="%.9f" alt="%.1fM" surface="%s"'
          ' heading="%.3f" length="%.1fM" width="%.1fM" number="%s" designator="%s"'
          ' patternAltitude="1500.0F" primaryTakeoff="YES" primaryLanding="YES"'
          ' primaryPattern="LEFT" secondaryTakeoff="YES" secondaryLanding="YES"'
          ' secondaryPattern="RIGHT">'
          % (lat, lon, ELEV_M, surf(r['tags']), hdg, r['len'], r['width'],
             num, {'L': 'LEFT', 'R': 'RIGHT', 'C': 'CENTER'}.get(desig, 'NONE')))
        A('      <Markings edges="TRUE" threshold="TRUE" fixedDistance="TRUE"'
          ' touchdown="TRUE" dashes="TRUE" ident="TRUE" precision="TRUE"'
          ' edgePavement="TRUE" singleEnd="FALSE"/>')
        A('      <Lights center="MEDIUM" edge="MEDIUM" centerRed="TRUE"/>')
        A('    </Runway>')

    # ---- taxiway network ------------------------------------------------
    # dedupe endpoints onto a 0.5 m grid so shared junctions become one node
    idx, pts = {}, []

    def node_of(p):
        k = (round(p[0] * 2), round(p[1] * 2))
        if k not in idx:
            idx[k] = len(pts)
            pts.append(p)
        return idx[k]

    paths, names, name_idx = [], [], {}
    for w in ways:
        if w['kind'] != 'taxiway' or len(w['pts']) < 2:
            continue
        ref = w['tags'].get('ref') or w['tags'].get('name')
        if ref:
            if ref not in name_idx:
                name_idx[ref] = len(names)
                names.append(ref)
            nid = name_idx[ref]
        else:
            nid = None
        try:
            wid = float(str(w['tags'].get('width', 23)).split()[0])
        except ValueError:
            wid = 23.0
        chainpts = [node_of(p) for p in w['pts']]
        for i in range(len(chainpts) - 1):
            if chainpts[i] != chainpts[i + 1]:
                paths.append((chainpts[i], chainpts[i + 1], wid, surf(w['tags']), nid))

    for i, p in enumerate(pts):
        lat, lon = to_ll(*p)
        A('    <TaxiwayPoint index="%d" type="NORMAL" orientation="FORWARD"'
          ' lat="%.9f" lon="%.9f"/>' % (i, lat, lon))

    for i, n in enumerate(names):
        A('    <TaxiwayName index="%d" name="%s"/>' % (i, escape(str(n))[:8]))

    # ---- parking stands --------------------------------------------------
    # a parking_position way is the lead-in line: the aircraft stops at its far
    # end, facing the way it was travelling
    parking = []
    for w in ways:
        if w['kind'] != 'parking_position' or len(w['pts']) < 2:
            continue
        stop, prev = w['pts'][-1], w['pts'][-2]
        parking.append((stop, bearing(prev, stop), w['tags'].get('ref', '')))

    for i, (p, hdg, ref) in enumerate(parking):
        lat, lon = to_ll(*p)
        digits = ''.join(ch for ch in ref if ch.isdigit())
        A('    <TaxiwayParking index="%d" lat="%.9f" lon="%.9f" heading="%.3f"'
          ' radius="24.0M" type="GATE_MEDIUM" name="GATE" number="%s"'
          ' pushBack="NONE" airlineCodes="">'
          % (i, lat, lon, hdg, digits or str(i)))
        A('    </TaxiwayParking>')

    for (s, e, wid, sf, nid) in paths:
        A('    <TaxiwayPath type="TAXI" start="%d" end="%d" width="%.1fM"'
          ' weightLimit="1000" surface="%s" drawSurface="TRUE" drawDetail="TRUE"'
          ' centerLine="TRUE" centerLineLighted="FALSE"%s/>'
          % (s, e, wid, sf, (' name="%d"' % nid) if nid is not None else ''))

    # ---- aprons ----------------------------------------------------------
    na = 0
    for w in ways + rels:
        if w['kind'] != 'apron' or len(w['pts']) < 4:
            continue
        A('    <Apron surface="CONCRETE" drawSurface="TRUE" drawDetail="TRUE">')
        for p in w['pts']:
            lat, lon = to_ll(*p)
            A('      <Vertex lat="%.9f" lon="%.9f"/>' % (lat, lon))
        A('    </Apron>')
        na += 1

    A('  </Airport>')
    A('</FSData>')

    open(out, 'w').write('\n'.join(L) + '\n')
    print('%s written' % out)
    print('  runways        %4d' % len(rwy))
    print('  taxiway nodes  %4d' % len(pts))
    print('  taxiway paths  %4d' % len(paths))
    print('  taxiway names  %4d' % len(names))
    print('  parking stands %4d' % len(parking))
    print('  aprons         %4d' % na)
    print('  lines          %4d' % len(L))


if __name__ == '__main__':
    main()
