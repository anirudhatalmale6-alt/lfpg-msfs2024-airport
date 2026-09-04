"""Perspective z-buffer rasteriser for the airport mesh.

Same approach as the paintkit renderer: project, cull, fill by barycentrics,
depth-test per pixel. Flat shading, because the point of these views is to
check that the geometry is in the right place, not to be pretty.
"""
import math, sys
import numpy as np
from PIL import Image

SUN = np.array([-0.42, 0.80, -0.43])
SUN /= np.linalg.norm(SUN)


ZNEAR = 2.0


def clip_near(cam, C):
    """Clip triangles against the near plane in camera space.

    Without this, any triangle with even one vertex behind the eye is dropped
    whole - which at ground level deletes the near field and leaves a band of
    sky under the horizon. Fully-visible triangles (the vast majority) pass
    through untouched; only the straddlers go round the slow path.
    """
    zc = -cam[:, :, 2]
    nin = (zc > ZNEAR).sum(axis=1)
    keep = cam[nin == 3]
    keepc = C[nin == 3]
    extra, extrac = [], []
    for i in np.nonzero((nin == 1) | (nin == 2))[0]:
        tri, zz = cam[i], zc[i]
        ins = [k for k in range(3) if zz[k] > ZNEAR]
        out = [k for k in range(3) if zz[k] <= ZNEAR]

        def cut(a, b):                       # a inside, b outside
            t = (zz[a] - ZNEAR) / (zz[a] - zz[b])
            return tri[a] + t * (tri[b] - tri[a])

        if len(ins) == 1:
            a = ins[0]
            extra.append(np.stack([tri[a], cut(a, out[0]), cut(a, out[1])]))
            extrac.append(C[i])
        else:
            a, b = ins
            p, q = cut(a, out[0]), cut(b, out[0])
            extra.append(np.stack([tri[a], tri[b], q]))
            extra.append(np.stack([tri[a], q, p]))
            extrac.extend([C[i], C[i]])
    if extra:
        keep = np.concatenate([keep, np.array(extra, np.float32)])
        keepc = np.concatenate([keepc, np.array(extrac, np.float32)])
    return keep, keepc


def render(V, C, eye, target, W=960, H=640, fov=52.0, ss=2):
    W, H = W * ss, H * ss
    eye = np.array(eye, np.float64)
    target = np.array(target, np.float64)

    fwd = target - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.array([0.0, 1.0, 0.0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    Rm = np.stack([right, up, -fwd])                    # world -> camera

    cam = (V - eye) @ Rm.T
    cam, C = clip_near(cam, C)
    z = -cam[:, :, 2]
    f = 1.0 / math.tan(math.radians(fov) / 2)
    with np.errstate(divide='ignore', invalid='ignore'):
        sx = (cam[:, :, 0] * f / z) * (H / 2) + W / 2
        sy = (-cam[:, :, 1] * f / z) * (H / 2) + H / 2

    # sky gradient
    img = np.zeros((H, W, 3), np.float32)
    g = np.linspace(0, 1, H)[:, None]
    img[:] = ((1 - g) * np.array([126, 160, 205]) + g * np.array([198, 214, 230]))[:, None, :]
    zbuf = np.full((H, W), 1e18)

    # shade from the clipped camera-space triangles, so take the sun with them
    sun_cam = Rm @ SUN
    nrm = np.cross(cam[:, 1] - cam[:, 0], cam[:, 2] - cam[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    nrm /= ln
    lam = np.abs(nrm @ sun_cam)
    shade = (0.42 + 0.58 * lam)[:, None]

    ok = (z > 1.0).all(axis=1)
    order = np.argsort(-z.min(axis=1))                  # far to near helps nothing
    drawn = 0
    for i in order:
        if not ok[i]:
            continue
        ax, ay = sx[i, 0], sy[i, 0]
        bx, by = sx[i, 1], sy[i, 1]
        cx, cy = sx[i, 2], sy[i, 2]
        x0 = int(max(0, math.floor(min(ax, bx, cx))))
        x1 = int(min(W - 1, math.ceil(max(ax, bx, cx))))
        y0 = int(max(0, math.floor(min(ay, by, cy))))
        y1 = int(min(H - 1, math.ceil(max(ay, by, cy))))
        if x1 < x0 or y1 < y0:
            continue
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        X = np.arange(x0, x1 + 1)[None, :] + 0.5
        Y = np.arange(y0, y1 + 1)[:, None] + 0.5
        l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den
        l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den
        l3 = 1.0 - l1 - l2
        ins = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not ins.any():
            continue
        zz = l1 * z[i, 0] + l2 * z[i, 1] + l3 * z[i, 2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        win = ins & (zz < sub)
        if not win.any():
            continue
        col = C[i] * shade[i]
        # thin aerial haze, so the far end of a 4 km runway recedes
        haze = np.clip((zz[win] - 900.0) / 26000.0, 0, 0.17)[:, None]
        px = col[None, :] * (1 - haze) + np.array([176, 196, 214])[None, :] * haze
        tgt = img[y0:y1 + 1, x0:x1 + 1]
        tgt[win] = px
        sub[win] = zz[win]
        drawn += 1

    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if ss > 1:
        out = out.resize((W // ss, H // ss), Image.LANCZOS)
    return out, drawn


if __name__ == '__main__':
    d = np.load('mesh.npz')
    V, C = d['V'], d['C']
    name = sys.argv[1]
    eye = tuple(float(v) for v in sys.argv[2:5])
    tgt = tuple(float(v) for v in sys.argv[5:8])
    fov = float(sys.argv[8]) if len(sys.argv) > 8 else 52.0
    im, n = render(V, C, eye, tgt, fov=fov)
    im.save(name, quality=94)
    print('%s  %s  %d tris drawn' % (name, im.size, n))
