"""ECOTAM wordmark generator: custom bold organic letters, warped into a toucan-beak envelope.
Internal coords: y-up, baseline y=0, cap height H. Every contour = list of cubic segments."""
import math, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)

H = 200.0          # cap height
S = 58.0           # vertical stem
SH = 46.0          # horizontal stroke (optically thinner)
GAP = 13.0         # tight tracking
OV = 5.0           # overshoot for round forms
KAPPA = 0.5523


class Pen:
    def __init__(self, x, y):
        self.start = (x, y); self.cur = (x, y); self.segs = []

    def L(self, x, y):
        x0, y0 = self.cur
        n = max(1, int(math.hypot(x - x0, y - y0) // 60))
        for i in range(n):
            a = (x0 + (x - x0) * i / n, y0 + (y - y0) * i / n)
            b = (x0 + (x - x0) * (i + 1) / n, y0 + (y - y0) * (i + 1) / n)
            self.segs.append(((a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3),
                              (a[0] + 2 * (b[0] - a[0]) / 3, a[1] + 2 * (b[1] - a[1]) / 3), b))
        self.cur = (x, y); return self

    def C(self, x1, y1, x2, y2, x, y):
        self.segs.append(((x1, y1), (x2, y2), (x, y))); self.cur = (x, y); return self

    def arc(self, cx, cy, rx, ry, a0, a1):
        """elliptical arc, degrees, any direction, split <=90deg."""
        n = max(1, int(math.ceil(abs(a1 - a0) / 90 - 1e-9)))
        d = math.radians((a1 - a0) / n)
        k = 4 / 3 * math.tan(d / 4)
        for i in range(n):
            t0 = math.radians(a0) + d * i; t1 = t0 + d
            p0 = (cx + rx * math.cos(t0), cy + ry * math.sin(t0))
            p1 = (cx + rx * math.cos(t1), cy + ry * math.sin(t1))
            c1 = (p0[0] - k * rx * math.sin(t0), p0[1] + k * ry * math.cos(t0))
            c2 = (p1[0] + k * rx * math.sin(t1), p1[1] - k * ry * math.cos(t1))
            self.segs.append((c1, c2, p1))
        self.cur = self.segs[-1][2]; return self

    def close(self):
        if math.hypot(self.cur[0] - self.start[0], self.cur[1] - self.start[1]) > 0.01:
            self.L(*self.start)
        return (self.start, self.segs)


def area(c):
    pts = [c[0]] + [s[2] for s in c[1]]
    return sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1)) / 2


def orient(c, outer):
    a = area(c)
    if (a > 0) == outer:
        return c
    start, segs = c
    pts = [start] + [s[2] for s in segs]
    nsegs = []
    for i in range(len(segs) - 1, -1, -1):
        c1, c2, p = segs[i]
        nsegs.append((c2, c1, pts[i]))
    return (pts[-1], nsegs)


def shift(contours, dx, dy=0):
    f = lambda p: (p[0] + dx, p[1] + dy)
    return [(f(s), [(f(a), f(b), f(c)) for a, b, c in segs], o) for s, segs, o in contours]


# ---------- glyphs (each returns width, [(start, segs, is_outer)]) ----------
def g_E(w=150, mid_arm=0.84):
    r = 70
    p = Pen(w, H)
    p.L(r, H).C(r * (1 - KAPPA), H, 0, H - r * (1 - KAPPA) - r * KAPPA * 0 + 0, 0, H - r)
    p.L(0, r).C(0, r * (1 - KAPPA), r * (1 - KAPPA), 0, r, 0)
    p.L(w, 0).L(w - 4, SH)
    ri = 16; ym = H / 2 + 2; hm = SH * 0.94
    p.L(S + ri, SH).C(S + ri * (1 - KAPPA), SH, S, SH + ri * (1 - KAPPA), S, SH + ri)
    p.L(S, ym - hm / 2).L(w * mid_arm, ym - hm / 2).L(w * mid_arm - 3, ym + hm / 2).L(S, ym + hm / 2)
    p.L(S, H - SH - ri).C(S, H - SH - ri * (1 - KAPPA), S + ri * (1 - KAPPA), H - SH, S + ri, H - SH)
    p.L(w - 4, H - SH)
    c = p.close()
    return w, [(c[0], c[1], True)]


def g_O(w=190):
    cx, cy = w / 2, H / 2
    rx, ry = w / 2, H / 2 + OV
    o = Pen(cx + rx, cy).arc(cx, cy, rx, ry, 0, 360).close()
    ix, iy = rx - S * 1.02, ry - SH
    i = Pen(cx + ix, cy).arc(cx, cy, ix, iy, 0, 360).close()
    return w, [(o[0], o[1], True), (i[0], i[1], False)]


def g_C(w=172, ang=46):
    cx, cy = w / 2 + 4, H / 2
    rx, ry = w / 2 + 4, H / 2 + OV
    ix, iy = rx - S * 1.02, ry - SH
    a0, a1 = ang, 360 - ang
    p = Pen(cx + rx * math.cos(math.radians(a0)), cy + ry * math.sin(math.radians(a0)))
    p.arc(cx, cy, rx, ry, a0, a1)
    p.L(cx + ix * math.cos(math.radians(a1 + 6)), cy + iy * math.sin(math.radians(a1 + 6)))
    p.arc(cx, cy, ix, iy, a1 + 6, a0 - 6 + 360 - 360)
    c = p.close()
    return w - 6, [(c[0], c[1], True)]


def g_T(w=156, stem_only=False, bar_h=None):
    sx = w / 2 - S / 2
    out = []
    if stem_only:
        p = Pen(sx, 0).L(sx + S, 0).L(sx + S, H - 10).L(sx, H - 10)
        c = p.close(); out.append((c[0], c[1], True))
        return w, out
    p = Pen(sx, 0).L(sx + S, 0).L(sx + S, H - SH - 10)
    p.C(sx + S, H - SH - 2, sx + S + 6, H - SH, sx + S + 16, H - SH)
    p.L(w, H - SH).L(w - 2, H).L(2, H).L(0, H - SH).L(sx - 16, H - SH)
    p.C(sx - 6, H - SH, sx, H - SH - 2, sx, H - SH - 10)
    c = p.close(); out.append((c[0], c[1], True))
    return w, out


def g_A(w=178):
    """pointed ogive A: curved legs, pointed apex (aerodynamic, organic)."""
    yb = H * 0.22; yt = yb + SH * 0.92
    ap = H + OV + 2
    p = Pen(0, 0).L(0, H * 0.30)
    p.C(0, H * 0.70, w * 0.30, H * 0.93, w / 2, ap)
    p.C(w * 0.70, H * 0.93, w, H * 0.70, w, H * 0.30)
    p.L(w, 0).L(w - S, 0).L(w - S, yb).L(S, yb).L(S, 0)
    o = p.close()
    iap = ap - S * 1.18
    q = Pen(S, yt).L(w - S, yt).L(w - S, H * 0.34)
    q.C(w - S, H * 0.60, w * 0.60, iap, w / 2, iap)
    q.C(w * 0.40, iap, S, H * 0.60, S, H * 0.34)
    i = q.close()
    return w, [(o[0], o[1], True), (i[0], i[1], False)]


def g_M(w=214, tip=False):
    """rounded shoulders, pointed middle. tip=True: right stem ends in a down-hooked beak point."""
    sh = w * 0.27
    p = Pen(0, 0).L(0, H * 0.58)
    p.C(0, H * 0.88, sh * 0.42, H + OV, sh, H + OV)                         # left shoulder top
    p.C(sh * 1.5, H + OV, w * 0.45, H * 0.80, w / 2, H * 0.50)            # down into notch
    p.C(w * 0.55, H * 0.80, w - sh * 1.5, H + OV, w - sh, H + OV)          # up right shoulder
    p.C(w - sh * 0.42, H + OV, w, H * 0.88, w, H * 0.58)
    if tip:
        p.C(w, H * 0.20, w + 10, H * 0.02, w + 34, -H * 0.30)             # outer edge sweeps to hooked tip
        p.C(w + 2, -H * 0.16, w - S * 0.7, -H * 0.04, w - S, 0)
    else:
        p.L(w, 0).L(w - S, 0)
    p.L(w - S, H * 0.56)
    p.C(w - S, H * 0.70, w - sh * 1.15, H * 0.74, w * 0.57, H * 0.34)      # inner right
    p.L(w / 2, H * 0.14)                                                    # inner notch bottom
    p.L(w * 0.43, H * 0.34)
    p.C(sh * 1.15, H * 0.74, S, H * 0.70, S, H * 0.56)
    p.L(S, 0)
    c = p.close()
    return w, [(c[0], c[1], True)]


# ---------- layout + warp ----------
def set_word(glyphs, gap=GAP):
    x = 0; out = []; boxes = []
    for w, cs in glyphs:
        out += shift(cs, x); boxes.append((x, x + w)); x += w + gap
    return x - gap, out, boxes


def warp(contours, fx):
    f = lambda p: (p[0], p[1] * fx(p[0]))
    return [(f(s), [(f(a), f(b), f(c)) for a, b, c in segs], o) for s, segs, o in contours]


def warp2(contours, top, bot):
    def f(p):
        t, b = top(p[0]), bot(p[0])
        return (p[0], b + p[1] / H * (t - b))
    return [(f(s), [(f(a), f(b), f(c)) for a, b, c in segs], o) for s, segs, o in contours]


def env(L, drop=0.27, power=1.9):
    return lambda x: 1.0 - drop * max(0.0, min(1.2, x / L)) ** power


def to_d(contours, sx, sy, ox, oy):
    parts = []
    for start, segs, outer in contours:
        start, segs = orient((start, segs), outer)
        P = lambda p: f"{ox + p[0] * sx:.2f} {oy - p[1] * sy:.2f}"
        parts.append("M" + P(start) + "".join(("L" + P(c)) if b == c else ("C" + P(a) + " " + P(b) + " " + P(c)) for a, b, c in segs) + "Z")
    return "".join(parts)


def bbox(contours):
    xs, ys = [], []
    for start, segs, _ in contours:
        for p in [start] + [q for s in segs for q in s]:
            xs.append(p[0]); ys.append(p[1])
    return min(xs), min(ys), max(xs), max(ys)


def flatten(start, segs, step=24):
    pts = [start]; p0 = start
    for c1, c2, p in segs:
        for i in range(1, step + 1):
            t = i / step; u = 1 - t
            pts.append((u**3*p0[0] + 3*u*u*t*c1[0] + 3*u*t*t*c2[0] + t**3*p[0],
                        u**3*p0[1] + 3*u*u*t*c1[1] + 3*u*t*t*c2[1] + t**3*p[1]))
        p0 = p
    return pts


def solidify(contours, cuts=()):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    outs = [Polygon(flatten(s, g)).buffer(0) for s, g, o in contours if o]
    holes = [Polygon(flatten(s, g)).buffer(0) for s, g, o in contours if not o]
    geo = unary_union(outs)
    for h in holes + list(cuts):
        geo = geo.difference(h)
    return geo.simplify(0.15)


def geo_contours(geo):
    polys = getattr(geo, "geoms", [geo])
    out = []
    for poly in polys:
        for ring, outer in [(poly.exterior, True)] + [(r, False) for r in poly.interiors]:
            pts = list(ring.coords)
            p = Pen(*pts[0]); p.segs = []
            for q in pts[1:]:
                p.segs.append((p.cur, q, q)); p.cur = q
            out.append((pts[0], p.segs, outer))
    return out


def write_svg(name, contours, title, height=256, pad=0.10, square=False, cuts=()):
    contours = geo_contours(solidify(contours, cuts))
    x0, y0, x1, y1 = bbox(contours)
    bw, bh = x1 - x0, y1 - y0
    if square:
        side = 256; s = side * (1 - 2 * pad) / max(bw, bh)
        W, Hh = side, side
        ox = (side - bw * s) / 2 - x0 * s; oy = (side + bh * s) / 2 + y0 * s - side * 0.01
    else:
        s = height * (1 - 2 * pad) / bh
        W = bw * s + 2 * pad * height; Hh = height
        ox = pad * height - x0 * s; oy = height - pad * height + y0 * s
    d = to_d(contours, s, s, ox, oy)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {Hh:.0f}" width="{W:.0f}" height="{Hh:.0f}" '
           f'role="img" aria-labelledby="t"><title id="t">{title}</title><path fill="#0F1012" d="{d}"/></svg>\n')
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(svg)


def word_glyphs(tip):
    return [g_E(), g_C(), g_O(), g_T(), g_A(), g_M(tip=tip)]


# ===== Concept A — "Perfil": tapered beak envelope, pointed M tip =====
L, cs, boxes = set_word(word_glyphs(tip=True), gap=11)
A_word = warp(cs, env(L, drop=0.36, power=1.6))
write_svg("a-wordmark.svg", A_word, "ECOTAM — conceito A")
# symbol A: the E alone, tapered, lower arm hooking into the beak tip
def e_tip():
    w, cs = g_E()
    p = Pen(130, 0).L(160, 0).C(184, 0, 202, -14, 210, -56).C(194, -28, 176, SH, 148, SH).L(130, SH)
    t = p.close()
    return cs + [(t[0], t[1], True)]
write_svg("a-symbol.svg", warp(e_tip(), env(210, drop=0.30, power=1.4)), "ECOTAM símbolo A", square=True, pad=0.12)

# ===== Concept B — "Cúlmen": T crossbar becomes the beak's ridge over A and M =====
gl = [g_E(), g_C(), g_O(), g_T(stem_only=True), g_A(), g_M(tip=False)]
L, cs, boxes = set_word(gl)
tx0, tx1 = boxes[3]
tip_x = L + 58
E_ = env(L + 40, drop=0.30, power=1.6)
top = lambda x: H * E_(x)
gapb = 15


def bar_th(x):
    t = max(0.0, min(1.0, (x - tx0) / (tip_x - tx0)))
    return SH * 1.1 * (1.0 - 0.25 * t)


# split: glyph contours before T keep envelope; A/M shrink below the bar
def fxB(x):
    if x < boxes[4][0] - GAP / 2:
        return E_(x) if x < tx0 else E_(x)
    return (top(x) - bar_th(x) - gapb) / H
B_letters = warp(cs, fxB)
# bar: top edge follows envelope from T's left to tip, then hooks down to a point
xs = [tx0 + (tip_x - tx0) * i / 12 for i in range(13)]
p = Pen(tx0, top(tx0))
for x in xs[1:-2]:
    p.L(x, top(x))
# hooked tip
xe = xs[-2]
p.C(xe + 30, top(xe) - 2, tip_x + 18, top(xe) - 30, tip_x + 22, top(xe) - 74)
p.C(tip_x - 2, top(xe) - 46, xe - 10, top(xe) - bar_th(xe) - 2, xe - 40, top(xe - 40) - bar_th(xe - 40))
for x in reversed(xs[:-3]):
    p.L(x, top(x) - bar_th(x))
p.L(tx0, top(tx0) - SH)
bar = p.close()
# stem of T reaches into the bar
B_word = B_letters + [(bar[0], bar[1], True)]
write_svg("b-wordmark.svg", B_word, "ECOTAM — conceito B")
# symbol B: T + ridge hook alone, compact
_, symT, bx = set_word([g_T(stem_only=True)])
sym_b = warp(symT, lambda x: 1.0)
q = Pen(-10, H)
q.L(60, H).L(110, H - 4)
q.C(150, H - 8, 186, H - 40, 192, H - 104)
q.C(170, H - 70, 140, H - SH - 6, 104, H - SH - 4)
q.L(60, H - SH).L(-10, H - SH).L(-18, H - SH * 0.5)
symbar = q.close()
sym_b = shift([(c[0], c[1], c[2]) for c in symT], 0) + [(symbar[0], symbar[1], True)]
# E beside it for a two-letter seal reads poorly; keep T-ridge as the icon
write_svg("b-symbol.svg", sym_b, "ECOTAM símbolo B", square=True, pad=0.14)

# ===== Concept C — "Silhueta": letters touch; top ridge falls, lower edge rises = one beak outline =====
L, cs, boxes = set_word(word_glyphs(tip=True), gap=1)
topC = lambda x: H * (1.0 - 0.34 * max(0, min(1.15, x / L)) ** 1.5)
botC = lambda x: H * (0.10 * max(0, min(1.15, x / L)) ** 2.2)
C_word = warp2(cs, topC, botC)
from shapely.geometry import LineString
xs_ = [-40 + i * (L * 0.86 + 40) / 80 for i in range(81)]
comm = lambda x: H * (0.31 - 0.25 * max(0, min(1.1, x / L)) ** 1.8)
cut = LineString([(x, comm(x)) for x in xs_]).buffer(5, cap_style=1)
C_word = warp(cs, env(L, drop=0.36, power=1.6))
write_svg("c-wordmark.svg", C_word, "ECOTAM — conceito C", cuts=[cut])
band_t = SH * 0.8
# symbol C: same E with the commissure cut
cutE = LineString([(x, H * (0.31 - 0.30 * max(0, x / 210) ** 1.6)) for x in range(-30, 140, 5)]).buffer(6, cap_style=1)
write_svg("c-symbol.svg", warp(e_tip(), env(210, drop=0.30, power=1.4)), "ECOTAM símbolo C", square=True, pad=0.12, cuts=[cutE])
print("ok", OUT)
