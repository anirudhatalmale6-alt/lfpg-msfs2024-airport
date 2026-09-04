"""Load the LFPG OSM extract and project it to metres on a local ENU frame.

Everything downstream works in metres east/north of the aerodrome reference
point, because that is the frame the sim's airport XML wants and the frame
you can sanity-check against the published runway lengths.
"""
import json, math

ARP_LAT, ARP_LON = 49.00969, 2.54792          # LFPG aerodrome reference point
R = 6378137.0


def to_xy(lat, lon):
    """Equirectangular about the ARP. Over 6 km of airport the error is < 0.1 m."""
    x = math.radians(lon - ARP_LON) * R * math.cos(math.radians(ARP_LAT))
    y = math.radians(lat - ARP_LAT) * R
    return x, y


def load(path='lfpg.json'):
    d = json.load(open(path))
    ways, nodes, rels = [], [], []
    for e in d['elements']:
        t = e.get('tags', {})
        kind = t.get('aeroway')
        if e['type'] == 'node':
            x, y = to_xy(e['lat'], e['lon'])
            nodes.append({'kind': kind, 'tags': t, 'xy': (x, y)})
        elif e['type'] == 'way' and e.get('geometry'):
            pts = [to_xy(g['lat'], g['lon']) for g in e['geometry']]
            ways.append({'kind': kind, 'tags': t, 'pts': pts, 'id': e['id']})
        elif e['type'] == 'relation':
            # multipolygon: take the outer members, each already carrying geometry
            for m in e.get('members', []):
                if m.get('role') == 'outer' and m.get('geometry'):
                    pts = [to_xy(g['lat'], g['lon']) for g in m['geometry']]
                    rels.append({'kind': kind, 'tags': t, 'pts': pts, 'id': e['id']})
    return ways, nodes, rels


def polylen(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


if __name__ == '__main__':
    ways, nodes, rels = load()
    print('ways %d  nodes %d  relation-outers %d' % (len(ways), len(nodes), len(rels)))
    xs = [p[0] for w in ways for p in w['pts']]
    ys = [p[1] for w in ways for p in w['pts']]
    print('extent  east %8.0f .. %8.0f   north %8.0f .. %8.0f  (m)'
          % (min(xs), max(xs), min(ys), max(ys)))
    print('site    %.0f m x %.0f m' % (max(xs) - min(xs), max(ys) - min(ys)))
    print()
    print('%-12s %8s %8s %6s  %s' % ('RUNWAY', 'measured', 'published', 'width', 'bearing'))
    for w in ways:
        if w['kind'] != 'runway' or not w['tags'].get('ref'):
            continue
        a, b = w['pts'][0], w['pts'][-1]
        brg = (math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))) % 360
        print('%-12s %8.0f %8s %6s  %5.1f deg true'
              % (w['tags']['ref'], polylen(w['pts']),
                 w['tags'].get('length', '?'), w['tags'].get('width', '?'), brg))
