"""Lapisan gambar yang tidak bergantung resolusi.

Seluruh tata letak ditulis dalam koordinat logis 1280x800. Modul ini
mengalikannya dengan faktor skala K sesuai ukuran jendela, sehingga garis
dan teks digambar langsung pada resolusi asli (tajam, tidak terhimpit).
"""
import pygame

BASE_W, BASE_H = 1280, 800
K = 1.0
OX = OY = 0


def setup(win_w, win_h):
    """Hitung skala & offset (letterbox) untuk ukuran jendela saat ini."""
    global K, OX, OY
    K = min(win_w / BASE_W, win_h / BASE_H)
    OX = int((win_w - BASE_W * K) / 2)
    OY = int((win_h - BASE_H * K) / 2)


def P(p):
    return (OX + p[0] * K, OY + p[1] * K)


def R(r):
    x, y, w, h = r
    return pygame.Rect(round(OX + x * K), round(OY + y * K), max(1, round(w * K)), max(1, round(h * K)))


def W(w):
    return max(1, round(w * K)) if w else 0


def to_logical(pos):
    return ((pos[0] - OX) / K, (pos[1] - OY) / K)


def mouse_pos():
    return to_logical(pygame.mouse.get_pos())


def font_px(size):
    return max(8, round(size * K))


# ---- primitif ----
def line(s, c, a, b, w=1):
    pygame.draw.line(s, c, P(a), P(b), W(w))


def lines(s, c, closed, pts, w=1):
    pygame.draw.lines(s, c, closed, [P(p) for p in pts], W(w))


def polygon(s, c, pts, w=0):
    pygame.draw.polygon(s, c, [P(p) for p in pts], W(w))


def circle(s, c, center, r, w=0):
    pygame.draw.circle(s, c, P(center), max(1, r * K), W(w))


def rect(s, c, r, w=0, border_radius=0):
    pygame.draw.rect(s, c, R(r), W(w), border_radius=round(border_radius * K))


def ellipse(s, c, r, w=0):
    pygame.draw.ellipse(s, c, R(r), W(w))


def alpha_rect(s, rgba, r):
    rr = R(r)
    surf = pygame.Surface(rr.size, pygame.SRCALPHA)
    surf.fill(rgba)
    s.blit(surf, rr.topleft)


def clip(s, r):
    s.set_clip(R(r) if r is not None else None)


# ---- teks ----
def text(s, font, txt, color, **anchor):
    """Gambar teks. anchor: salah satu atribut Rect (topleft, center, midleft, ...)
    dalam koordinat logis. Default: topleft=(0,0)."""
    img = font.render(txt, True, color)
    key, val = next(iter(anchor.items())) if anchor else ("topleft", (0, 0))
    rr = img.get_rect(**{key: P(val)})
    s.blit(img, rr)


def text_size(font, txt):
    w, h = font.size(txt)
    return w / K, h / K
