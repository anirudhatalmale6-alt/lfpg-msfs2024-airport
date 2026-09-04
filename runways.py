"""Runway ways in OSM are split wherever another way crosses them, so a raw
way length is not the runway length. Chain the segments end-to-end first, then
measure. The published lengths are the check that the chaining is right.
"""
import math
from geo import load, polylen

TOL = 5.0            # metres; endpoints closer than this are the same point


def chain(ways):
    segs = [list(w['pts']) for w in ways]
    tags = [w['tags'] for w in ways]
    used = [False] * len(segs)
    out = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        cur, ct = list(segs[i]), dict(tags[i])
        grew = True
        while grew:
            grew = False
            for j in range(len(segs)):
                if used[j]:
                    continue
                s = segs[j]
                for a, b, rev in ((cur[-1], s[0], False), (cur[-1], s[-1], True),
                                  (cur[0], s[-1], False), (cur[0], s[0], True)):
                    if math.dist(a, b) > TOL:
                        continue
                    piece = list(reversed(s)) if rev else list(s)
                    if math.dist(cur[-1], b) <= TOL:
                        cur = cur + piece[1:]
                    else:
                        cur = list(reversed(piece))[:-1] + cur
                    used[j] = True
                    for k, v in tags[j].items():
                        ct.setdefault(k, v)
                    grew = True
                    break
                if grew:
                    break
        out.append({'pts': cur, 'tags': ct})
    return out


def runways(ways):
    raw = [w for w in ways
           if w['kind'] == 'runway' and w['tags'].get('surface') != 'grass']
    rw = [r for r in chain(raw) if polylen(r['pts']) > 1000]
    for r in rw:
        a, b = r['pts'][0], r['pts'][-1]
        r['len'] = polylen(r['pts'])
        r['brg'] = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360
        r['width'] = float(r['tags'].get('width', 45))
        r['ref'] = r['tags'].get('ref', '?')
        r['a'], r['b'] = a, b
    rw.sort(key=lambda r: -r['pts'][0][1])
    return rw


if __name__ == '__main__':
    ways, nodes, rels = load()
    print('%-12s %9s %10s %7s %6s   %s'
          % ('RUNWAY', 'measured', 'published', 'error', 'width', 'true bearing'))
    for r in runways(ways):
        pub = r['tags'].get('length')
        err = ('%+.1f%%' % ((r['len'] - float(pub)) / float(pub) * 100)) if pub else '-'
        print('%-12s %8.0fm %9sm %7s %5.0fm   %5.1f deg'
              % (r['ref'], r['len'], pub or '?', err, r['width'], r['brg']))
