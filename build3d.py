"""Turn the projected 2D layout into 3D triangles.

Ground surfaces are laid flat with a small vertical stagger so they never
z-fight; buildings are extruded from their real footprints. Heights come from
the tags where they exist and from a per-type default where they do not - which
is the honest position, since OSM does not carry a height for most of them.
"""
import math
import numpy as np
from geo import load
from runways import runways

# ground layers, metres above datum - ordered so the paint sits on the slab
Z_GRASS, Z_APRON, Z_TAXI, Z_RWY, Z_MARK = 0.00, 0.06, 0.10, 0.14, 0.20

COL = {
    'grass':   (104, 126, 78),
    'apron':   (168, 170, 166),
    'taxi':    (158, 160, 154),
    'rwy':     (72, 74, 78),
    'mark':    (226, 226, 220),
    'taximark': (206, 176, 66),
    'roof':    (198, 200, 202),
    'wall':    (156, 161, 168),
    'glass':   (120, 146, 172),
    'hangar':  (176, 178, 176),
    'tower':   (206, 202, 196),
}

DEFAULT_H = {'terminal': 19.0, 'hangar': 21.0, 'tower': 64.0}


def signed_area(p):
    s = 0.0
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        s += a[0] * b[1] - b[0] * a[1]
    return s / 2


def earclip(poly):
    """Ear clipping for a simple polygon. n is small here (tens of vertices)."""
    idx = list(range(len(poly)))
    if signed_area(poly) < 0:
        idx.reverse()
    tris, guard = [], 0
    while len(idx) > 2 and guard < 5000:
        guard += 1
        clipped = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cr <= 1e-9:
                continue
            bad = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = poly[j]
                d1 = (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])
                d2 = (c[0]-b[0])*(p[1]-b[1]) - (c[1]-b[1])*(p[0]-b[0])
                d3 = (a[0]-c[0])*(p[1]-c[1]) - (a[1]-c[1])*(p[0]-c[0])
                if d1 >= 0 and d2 >= 0 and d3 >= 0:
                    bad = True
                    break
            if bad:
                continue
            tris.append((a, b, c))
            idx.pop(k)
            guard, clipped = 0, True
            break
        if not clipped:
            break
    return tris


def strip(pts, width, z, tris, col):
    """A polyline laid flat as a ribbon of quads, mitre-free (good enough at
    these widths; the joints overlap rather than gap)."""
    h = width / 2.0
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        nx, ny = -dy / L * h, dx / L * h
        p = [(ax + nx, z, ay + ny), (bx + nx, z, by + ny),
             (bx - nx, z, by - ny), (ax - nx, z, ay - ny)]
        tris.append((p[0], p[1], p[2], col))
        tris.append((p[0], p[2], p[3], col))


def extrude(poly, h, tris, roof, wall):
    for (a, b, c) in earclip(poly):
        tris.append(((a[0], h, a[1]), (b[0], h, b[1]), (c[0], h, c[1]), roof))
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        # shade walls by orientation so the massing reads
        ang = math.atan2(by - ay, bx - ax)
        k = 0.80 + 0.20 * abs(math.cos(ang))
        w = tuple(int(min(255, v * k)) for v in wall)
        p0, p1 = (ax, 0.0, ay), (bx, 0.0, by)
        p2, p3 = (bx, h, by), (ax, h, ay)
        tris.append((p0, p1, p2, w))
        tris.append((p0, p2, p3, w))


def height_of(tags, kind):
    for key in ('height', 'building:height'):
        if key in tags:
            try:
                return float(str(tags[key]).split()[0])
            except ValueError:
                pass
    for key in ('building:levels', 'levels'):
        if key in tags:
            try:
                return float(str(tags[key]).split()[0]) * 4.2 + 3.0
            except ValueError:
                pass
    return DEFAULT_H.get(kind, 12.0)


def build():
    ways, nodes, rels = load()
    rwy = runways(ways)
    tris = []

    drawn = [w for w in ways + rels if w['kind'] != 'aerodrome']
    xs = [p[0] for w in drawn for p in w['pts']]
    ys = [p[1] for w in drawn for p in w['pts']]
    pad = 30000
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    # tessellated, not one big quad: the renderer has no near-plane clipper, so
    # a triangle with a vertex behind the camera is dropped whole. At ground
    # level that silently deletes the entire world.
    N = 64
    gx = np.linspace(x0, x1, N + 1)
    gy = np.linspace(y0, y1, N + 1)
    for i in range(N):
        for j in range(N):
            a = (gx[i], Z_GRASS, gy[j])
            b = (gx[i + 1], Z_GRASS, gy[j])
            c = (gx[i + 1], Z_GRASS, gy[j + 1])
            e = (gx[i], Z_GRASS, gy[j + 1])
            tris.append((a, b, c, COL['grass']))
            tris.append((a, c, e, COL['grass']))

    for w in ways + rels:
        if w['kind'] not in ('apron', 'hangar'):
            continue
        if len(w['pts']) < 4:
            continue
        for (a, b, c) in earclip(w['pts'][:-1] if w['pts'][0] == w['pts'][-1] else w['pts']):
            tris.append(((a[0], Z_APRON, a[1]), (b[0], Z_APRON, b[1]),
                         (c[0], Z_APRON, c[1]), COL['apron']))

    for w in ways:
        if w['kind'] != 'taxiway' or len(w['pts']) < 2:
            continue
        try:
            wid = float(str(w['tags'].get('width', 23)).split()[0])
        except ValueError:
            wid = 23.0
        strip(w['pts'], wid, Z_TAXI, tris, COL['taxi'])
        strip(w['pts'], 0.30, Z_MARK, tris, COL['taximark'])

    for r in rwy:
        strip(r['pts'], r['width'], Z_RWY, tris, COL['rwy'])
        strip(r['pts'], 0.9, Z_MARK, tris, COL['mark'])
        # touchdown / edge stripes
        a, b = np.array(r['a']), np.array(r['b'])
        v = (b - a) / r['len']
        nvec = np.array([-v[1], v[0]])
        for side in (1, -1):
            e = [tuple(a + nvec * side * (r['width'] / 2 - 1.2)),
                 tuple(b + nvec * side * (r['width'] / 2 - 1.2))]
            strip(e, 0.9, Z_MARK, tris, COL['mark'])

    nb = 0
    for w in ways + rels:
        k = w['kind']
        if k not in ('terminal', 'tower'):
            continue
        poly = w['pts'][:-1] if w['pts'][0] == w['pts'][-1] else w['pts']
        if len(poly) < 3:
            continue
        h = height_of(w['tags'], k)
        extrude(poly, h, tris,
                COL['tower'] if k == 'tower' else COL['roof'],
                COL['tower'] if k == 'tower' else COL['wall'])
        nb += 1

    for w in ways + rels:
        if w['kind'] != 'hangar':
            continue
        poly = w['pts'][:-1] if w['pts'][0] == w['pts'][-1] else w['pts']
        if len(poly) < 3:
            continue
        extrude(poly, height_of(w['tags'], 'hangar'), tris, COL['hangar'], COL['hangar'])
        nb += 1

    print('buildings extruded: %d   triangles: %d' % (nb, len(tris)))
    V = np.array([[t[0], t[1], t[2]] for t in tris], np.float32)
    C = np.array([t[3] for t in tris], np.float32)
    return V, C


if __name__ == '__main__':
    V, C = build()
    np.savez_compressed('mesh.npz', V=V, C=C)
    print('mesh.npz', V.shape, C.shape)
