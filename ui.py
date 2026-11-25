"""Widget antarmuka sederhana untuk pygame: tombol, slider, checkbox.
Semua koordinat dalam satuan logis (lihat gfx.py)."""
import pygame
import gfx

# Palet warna
BG = (13, 16, 21)
PANEL = (21, 26, 34)
PANEL2 = (27, 33, 48)
LINE = (40, 48, 67)
TXT = (229, 233, 240)
MUT = (138, 147, 166)
ACC = (76, 194, 255)
SP = (255, 181, 71)
OK = (74, 222, 128)
BAD = (248, 113, 113)
COL_P = (96, 165, 250)
COL_I = (192, 132, 252)
COL_D = (52, 211, 153)
M1 = (244, 114, 182)
M2 = (163, 230, 53)


class Button:
    def __init__(self, rect, text, on_click, is_active=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.on_click = on_click
        self.is_active = is_active

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.on_click()
            return True
        return False

    def draw(self, surf, font):
        active = self.is_active() if self.is_active else False
        hover = self.rect.collidepoint(gfx.mouse_pos())
        gfx.rect(surf, ACC if active else PANEL2, self.rect, border_radius=5)
        gfx.rect(surf, ACC if (hover or active) else LINE, self.rect, 1, border_radius=5)
        gfx.text(surf, font, self.text, (0, 19, 29) if active else TXT, center=self.rect.center)


class Slider:
    """Slider dengan getter/setter sehingga selalu sinkron dengan nilai model.
    Klik/seret untuk mengubah, roda mouse untuk penyesuaian halus."""

    def __init__(self, rect, label, get, set_, vmin, vmax, step, fmt="{:.2f}", label_w=110, value_w=92):
        self.rect = pygame.Rect(rect)
        self.label, self.get, self.set = label, get, set_
        self.vmin, self.vmax, self.step = vmin, vmax, step
        self.fmt = fmt
        self.track = pygame.Rect(self.rect.x + label_w, self.rect.centery - 3,
                                 self.rect.w - label_w - value_w, 6)
        self.dragging = False

    def _set_from_x(self, px):
        r = (px - self.track.x) / self.track.w
        r = max(0.0, min(1.0, r))
        v = self.vmin + r * (self.vmax - self.vmin)
        v = round(v / self.step) * self.step
        self.set(max(self.vmin, min(self.vmax, v)))

    def handle(self, ev):
        hit = self.track.inflate(12, 16)
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and hit.collidepoint(ev.pos):
            self.dragging = True
            self._set_from_x(ev.pos[0])
            return True
        if ev.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(ev.pos[0])
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.dragging:
            self.dragging = False
            return True
        if ev.type == pygame.MOUSEWHEEL and self.rect.collidepoint(gfx.mouse_pos()):
            v = self.get() + ev.y * self.step
            self.set(max(self.vmin, min(self.vmax, round(v / self.step) * self.step)))
            return True
        return False

    def draw(self, surf, font):
        v = self.get()
        gfx.text(surf, font, self.label, MUT, midleft=(self.rect.x, self.rect.centery))
        gfx.rect(surf, BG, self.track, border_radius=3)
        r = (v - self.vmin) / (self.vmax - self.vmin) if self.vmax > self.vmin else 0
        r = max(0.0, min(1.0, r))
        if r > 0:
            gfx.rect(surf, ACC, (self.track.x, self.track.y, self.track.w * r, self.track.h), border_radius=3)
        gfx.circle(surf, TXT, (self.track.x + self.track.w * r, self.track.centery), 7)
        txt = self.fmt(v) if callable(self.fmt) else self.fmt.format(v)
        gfx.text(surf, font, txt, TXT, midleft=(self.track.right + 12, self.rect.centery))


class Checkbox:
    def __init__(self, rect, label, get, set_):
        self.rect = pygame.Rect(rect)
        self.label, self.get, self.set = label, get, set_

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.set(not self.get())
            return True
        return False

    def draw(self, surf, font):
        box = pygame.Rect(self.rect.x, self.rect.centery - 8, 16, 16)
        on = self.get()
        gfx.rect(surf, ACC if on else BG, box, border_radius=3)
        gfx.rect(surf, ACC if on else LINE, box, 1, border_radius=3)
        if on:
            gfx.lines(surf, (0, 19, 29), False,
                      [(box.x + 3, box.y + 8), (box.x + 7, box.y + 12), (box.x + 13, box.y + 4)], 2)
        gfx.text(surf, font, self.label, TXT, midleft=(box.right + 8, self.rect.centery))
