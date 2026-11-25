"""Lintasan line follower.

Lintasan disimpan dua kali:
- sebagai polyline rapat (titik tiap 5 mm) untuk menggambar, menghitung
  jarak robot ke garis, dan mendeteksi lap;
- sebagai bitmap (resolusi 2 mm/piksel) yang dibaca oleh sensor robot,
  persis seperti sensor pantulan membaca permukaan lintasan.
"""
import math
import pygame

from config import LINE_W

DS = 0.005    # jarak antar titik polyline [m]
RES = 0.002   # resolusi bitmap [m/piksel]
MARGIN = 0.25  # tepi alas lintasan [m]


def resample(pts, ds=DS):
    """Sampling ulang polyline tertutup dengan jarak titik seragam."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        L = math.dist(a, b)
        k = max(1, int(round(L / ds)))
        for j in range(k):
            out.append((a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k))
    return out


def fillet_polygon(verts, arc_step=0.008):
    """Poligon tertutup dengan sudut dibulatkan.
    verts: list (x, y, r). r = jari-jari tikungan [m], 0 = sudut tajam."""
    n = len(verts)
    pts = []
    for i in range(n):
        x0, y0, _ = verts[i - 1]
        x1, y1, r = verts[i]
        x2, y2, _ = verts[(i + 1) % n]
        L1, L2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
        d1 = ((x1 - x0) / L1, (y1 - y0) / L1)
        d2 = ((x2 - x1) / L2, (y2 - y1) / L2)
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        dot = d1[0] * d2[0] + d1[1] * d2[1]
        theta = math.atan2(abs(cross), dot)
        if r <= 0 or theta < 1e-3:
            pts.append((x1, y1))
            continue
        t = r * math.tan(theta / 2)
        tmax = 0.48 * min(L1, L2)
        if t > tmax:
            t = tmax
            r = t / math.tan(theta / 2)
        t1 = (x1 - d1[0] * t, y1 - d1[1] * t)
        s = 1 if cross > 0 else -1
        c = (t1[0] - d1[1] * s * r, t1[1] + d1[0] * s * r)
        a0 = math.atan2(t1[1] - c[1], t1[0] - c[0])
        m = max(2, int(r * theta / arc_step))
        for j in range(m + 1):
            a = a0 + s * theta * j / m
            pts.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return pts


def _oval():
    return fillet_polygon([(0, 0, 0.6), (2.6, 0, 0.6), (2.6, 1.3, 0.6), (0, 1.3, 0.6)])


def _figure8():
    a = 1.7
    pts = []
    N = 1600
    for k in range(N):
        t = 2 * math.pi * k / N
        d = 1 + math.sin(t) ** 2
        pts.append((a * math.cos(t) / d, a * math.sin(t) * math.cos(t) / d))
    # mulai di ujung kanan, berjalan berlawanan arah jarum jam
    return pts


def _square_turns():
    return fillet_polygon([
        (0, 0, 0.03), (1.5, 0, 0.25), (2.1, 0.55, 0.2), (2.7, 0, 0.25), (3.4, 0, 0.3),
        (3.4, 1.7, 0.0), (2.6, 1.7, 0.0), (2.6, 1.05, 0.0), (1.8, 1.05, 0.0),
        (1.8, 2.1, 0.3), (0.6, 2.1, 0.35), (0, 1.5, 0.03),
    ])


def _wave():
    verts = [(0.0, 0.0, 0.0), (3.6, 0.0, 0.6), (3.6, 1.6, 0.6)]
    x = 3.0
    while x > 0.6 + 1e-9:
        verts.append((x, 1.6 + 0.2 * math.sin(2 * math.pi * (3.0 - x) / 0.6), 0.0))
        x -= 0.05
    verts += [(0.6, 1.6, 0.0), (-0.6, 1.6, 0.6), (-0.6, 0.0, 0.6)]
    return fillet_polygon(verts)


# nama: (pembuat lintasan, titik start di bagian lurus)
TRACK_BUILDERS = {
    "Oval": (_oval, (1.3, 0.0)),
    "Angka 8": (_figure8, (0.9, 0.5)),
    "Siku": (_square_turns, (0.75, 0.0)),
    "Gelombang": (_wave, (1.5, 0.0)),
}


class Track:
    def __init__(self, name):
        self.name = name
        builder, start = TRACK_BUILDERS[name]
        pts = resample(builder())
        # putar daftar titik agar indeks 0 = garis start (di bagian lurus)
        k = min(range(len(pts)), key=lambda i: math.dist(pts[i], start))
        self.pts = pts[k:] + pts[:k]
        self.n = len(self.pts)
        # tangen tiap titik
        self.tan = []
        for i in range(self.n):
            a, b = self.pts[i - 1], self.pts[(i + 1) % self.n]
            L = math.dist(a, b) or 1.0
            self.tan.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L))
        self.length = sum(math.dist(self.pts[i], self.pts[(i + 1) % self.n]) for i in range(self.n))
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        self.bounds = (min(xs) - MARGIN, min(ys) - MARGIN, max(xs) + MARGIN, max(ys) + MARGIN)
        self._build_bitmap()

    def _build_bitmap(self):
        x0, y0, x1, y1 = self.bounds
        w, h = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
        surf = pygame.Surface((w, h))
        surf.fill((255, 255, 255))
        rad = LINE_W / 2 / RES
        for (x, y) in self.pts:
            pygame.draw.circle(surf, (0, 0, 0), ((x - x0) / RES, (y1 - y) / RES), rad)
        self.bitmap = surf
        self.bw, self.bh = w, h

    def is_line(self, x, y):
        x0, y0, x1, y1 = self.bounds
        px, py = int((x - x0) / RES), int((y1 - y) / RES)
        if 0 <= px < self.bw and 0 <= py < self.bh:
            return self.bitmap.get_at((px, py))[0] < 128
        return False

    def coverage(self, x, y, r=0.003):
        """Fraksi titik bidang pandang sensor (5 titik) yang mengenai garis hitam."""
        c = 0
        for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r)):
            if self.is_line(x + dx, y + dy):
                c += 1
        return c / 5.0

    def nearest(self, x, y, hint=None, back=40, ahead=120):
        """Indeks titik lintasan terdekat dan jarak lateral bertanda
        (positif = robot di kiri garis menurut arah lintasan)."""
        if hint is None:
            rng = range(self.n)
        else:
            rng = (i % self.n for i in range(hint - back, hint + ahead))
        best, bi = 1e9, 0
        for i in rng:
            px, py = self.pts[i]
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best:
                best, bi = d, i
        px, py = self.pts[bi]
        tx, ty = self.tan[bi]
        lat = tx * (y - py) - ty * (x - px)
        return bi, lat

    def start_pose(self):
        (x, y), (tx, ty) = self.pts[0], self.tan[0]
        return x, y, math.atan2(ty, tx)
