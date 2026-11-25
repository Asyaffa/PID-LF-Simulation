"""Simulasi PID Robot Line Follower — versi lokal (Python + pygame-ce).

Jalankan:  python main.py

Kontrol:
  Tombol lintasan (atas)        : Oval, Angka 8, Siku, Gelombang
  Spasi                         : jeda / lanjut
  R                             : reset (robot kembali ke garis start)
  Panah atas / bawah            : kecepatan dasar +5% / -5%
  1 2 3 4                       : kecepatan simulasi 0.25x 0.5x 1x 2x
  Roda mouse di area lintasan   : zoom (di titik kursor)
  Klik kanan / tengah + seret   : geser tampilan
  + / - / 0                     : zoom in / zoom out / tampilan penuh
  F                             : kamera mengikuti robot
  C                             : simpan data ke CSV (folder data/)
  S                             : simpan screenshot PNG (folder data/)
  F11                           : layar penuh
  Roda mouse di atas slider     : penyesuaian halus
"""
import csv
import math
import os
import sys
from datetime import datetime

# Windows: mode DPI-aware agar jendela tidak diregangkan sistem (buram/terhimpit)
if sys.platform == "win32":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import pygame

import gfx
from config import SimOptions, LINE_W, PLOT_WINDOW
from fonts import load_font
from sim import Simulation, PRESETS
from track import TRACK_BUILDERS, DS
from ui import (Button, Slider, Checkbox, BG, PANEL, PANEL2, LINE, TXT, MUT, ACC, SP,
                OK, BAD, COL_P, COL_I, COL_D, M1, M2)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

WIN_W, WIN_H = gfx.BASE_W, gfx.BASE_H
SIM_RECT = pygame.Rect(10, 52, 840, 400)
PANEL_RECT = pygame.Rect(860, 52, 410, 740)
MAT = (228, 228, 222)      # warna alas lintasan
INK = (18, 18, 18)         # warna garis


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Simulasi PID Line Follower")
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except Exception:
            dw, dh = 1600, 1000
        k0 = max(0.6, min(dw * 0.94 / WIN_W, dh * 0.88 / WIN_H))
        self.screen = pygame.display.set_mode((int(WIN_W * k0), int(WIN_H * k0)), pygame.RESIZABLE)
        self.fullscreen = False
        self.clock = pygame.time.Clock()
        self._font_k = None
        self.on_resize()

        self.opts = SimOptions()
        self.sim = Simulation(self.opts, "Oval")
        self.speed = 1.0
        self.paused = False
        self.tab = "PID"
        self.preset = "Seimbang"
        self.follow = False
        self.panning = None
        self.toast_text, self.toast_time = "", 0.0
        self.fit_view()
        self._build_widgets()

    # ------------------------------------------------------------ jendela
    def on_resize(self):
        self.screen = pygame.display.get_surface()
        gfx.setup(*self.screen.get_size())
        if self._font_k != gfx.K:
            self._font_k = gfx.K
            fp = gfx.font_px
            self.f_title = load_font("sans", fp(18), bold=True)
            self.f = load_font("sans", fp(14))
            self.f_s = load_font("sans", fp(12))
            self.f_xs = load_font("sans", fp(11))
            self.f_m = load_font("mono", fp(13))
            self.f_mb = load_font("mono", fp(16), bold=True)
            self._bg_cache = None

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self._win_size = self.screen.get_size()
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            pygame.display.set_mode(self._win_size, pygame.RESIZABLE)
        self.on_resize()

    # ------------------------------------------------------------ widget
    def _build_widgets(self):
        sim, o = self.sim, self.opts
        self.top = []
        x = 330

        def add(w, text, cb, active=None):
            nonlocal x
            self.top.append(Button((x, 10, w, 30), text, cb, active))
            x += w + 4

        for name, w in zip(TRACK_BUILDERS, (56, 72, 52, 88)):
            add(w, name, lambda n=name: self.set_track(n), lambda n=name: self.sim.track.name == n)
        x += 8
        for s, lab in ((0.25, "¼×"), (0.5, "½×"), (1.0, "1×"), (2.0, "2×")):
            add(36, lab, lambda s=s: setattr(self, "speed", s), lambda s=s: self.speed == s)
        x += 8
        add(56, "Jeda", self.toggle_pause, lambda: self.paused)
        add(56, "Reset", self.reset)
        add(96, "Simpan CSV", self.save_csv)

        bx, by = SIM_RECT.x + 10, SIM_RECT.bottom - 36
        self.sim_btns = [
            Button((bx, by, 30, 26), "−", lambda: self.set_zoom(self.zoom / 1.25)),
            Button((bx + 34, by, 30, 26), "+", lambda: self.set_zoom(self.zoom * 1.25)),
            Button((bx + 68, by, 48, 26), "Pas", self.fit_view),
            Button((bx + 120, by, 58, 26), "Ikuti", self.toggle_follow, lambda: self.follow),
        ]

        px, pw = PANEL_RECT.x + 10, PANEL_RECT.w - 20
        self.tabs = []
        tw = (pw - 12) // 4
        for i, name in enumerate(("PID", "Robot", "Gangguan", "Bantuan")):
            self.tabs.append(Button((px + i * (tw + 4), PANEL_RECT.y + 6, tw, 28), name,
                                    lambda n=name: setattr(self, "tab", n), lambda n=name: self.tab == n))
        self.widgets = {k: [] for k in ("PID", "Robot", "Gangguan", "Bantuan")}
        self.notes = {k: [] for k in self.widgets}
        Y0 = PANEL_RECT.y

        def slider(tab, y, label, get, set_, lo, hi, step, fmt, lw=152, vw=80):
            self.widgets[tab].append(Slider((px, y, pw, 26), label, get, set_, lo, hi, step, fmt,
                                            label_w=lw, value_w=vw))

        def opt_slider(tab, y, label, attr, lo, hi, step, fmt, mul=1.0, lw=152, vw=80):
            slider(tab, y, label, lambda: getattr(o, attr) * mul,
                   lambda v: setattr(o, attr, v / mul), lo, hi, step, fmt, lw, vw)

        def check(tab, y, label, attr, note=None):
            self.widgets[tab].append(Checkbox((px, y, pw, 22), label, lambda: getattr(o, attr),
                                              lambda v: setattr(o, attr, v)))
            if note:
                self.notes[tab].append((px + 24, y + 22, note))

        # ---- Tab PID ----
        W = self.widgets["PID"]
        bw = (pw - 4 * 4) // 5
        for i, name in enumerate(PRESETS):
            b = Button((px + i * (bw + 4), Y0 + 64, bw, 26), name,
                       lambda n=name: self.apply_preset(n), lambda n=name: self.preset == n)
            b.small = True
            W.append(b)
        self.pid_box = pygame.Rect(px, Y0 + 100, pw, 150)
        pid = sim.pid
        for j, (attr, lab, vmax, step, fmt) in enumerate((("kp", "Kp", 10, 0.05, "{:.2f}"),
                                                          ("ki", "Ki", 20, 0.1, "{:.1f}"),
                                                          ("kd", "Kd", 0.3, 0.002, "{:.3f}"))):
            W.append(Slider((px + 10, Y0 + 146 + j * 25, pw - 20, 24), lab,
                            lambda a=attr: getattr(pid, a), lambda v, a=attr: setattr(pid, a, v),
                            0, vmax, step, fmt, label_w=36, value_w=70))
        opt_slider("PID", Y0 + 262, "Kecepatan dasar", "base_speed", 0, 100, 1, lambda v: f"{v:.0f} %")
        check("PID", Y0 + 298, "Kurangi kecepatan di tikungan", "curve_slowdown",
              "Kecepatan dasar dikurangi sebanding dengan |e|.")
        opt_slider("PID", Y0 + 344, "   Pengurangan", "slowdown_k", 0, 0.9, 0.05,
                   lambda v: f"{v * 100:.0f} %")
        check("PID", Y0 + 384, "Ingat arah garis saat hilang", "line_memory",
              "Garis hilang → belok maksimal ke sisi terakhir garis terlihat.")
        check("PID", Y0 + 430, "Anti-windup (integrasi bersyarat)", "anti_windup")
        opt_slider("PID", Y0 + 466, "Frekuensi kendali", "control_hz", 20, 1000, 10, lambda v: f"{v:.0f} Hz")
        opt_slider("PID", Y0 + 500, "Filter turunan", "d_cutoff_hz", 1, 200, 1,
                   lambda v: "tanpa filter" if v >= 200 else f"{v:.0f} Hz")

        # ---- Tab Robot ----
        self.sensor_btns = []
        for i, n in enumerate((5, 8, 16)):
            b = Button((px + 152 + i * 56, Y0 + 66, 50, 26), str(n),
                       lambda n=n: self.set_sensors(n), lambda n=n: self.opts.n_sensors == n)
            self.widgets["Robot"].append(b)
        opt_slider("Robot", Y0 + 100, "Jarak antar sensor", "sensor_spacing_mm", 6, 25, 0.5, lambda v: f"{v:.1f} mm")
        opt_slider("Robot", Y0 + 134, "Jarak sensor ke roda", "sensor_offset_mm", 15, 150, 1, lambda v: f"{v:.0f} mm")
        opt_slider("Robot", Y0 + 208, "Jarak antar roda", "wheelbase_mm", 80, 250, 1, lambda v: f"{v:.0f} mm")
        opt_slider("Robot", Y0 + 242, "Kec. maks roda", "vmax", 0.5, 4.0, 0.05, lambda v: f"{v:.2f} m/s")
        opt_slider("Robot", Y0 + 276, "Waktu respons motor", "tau_motor", 10, 200, 1,
                   lambda v: f"{v:.0f} ms", mul=1000)
        opt_slider("Robot", Y0 + 310, "Gesekan ban μ", "mu", 0.3, 2.0, 0.05, lambda v: f"{v:.2f}")
        check("Robot", Y0 + 350, "Izinkan roda berputar mundur", "allow_reverse",
              "PWM negatif membantu menikung tajam (siku 90°).")

        # ---- Tab Gangguan ----
        opt_slider("Gangguan", Y0 + 70, "Noise sensor", "sensor_noise", 0, 0.4, 0.01, lambda v: f"σ {v:.2f}")
        opt_slider("Gangguan", Y0 + 104, "Efisiensi motor kiri", "motor_left_eff", 50, 150, 1,
                   lambda v: f"{v:.0f} %", mul=100)
        opt_slider("Gangguan", Y0 + 172, "Offset lateral awal", "init_offset_mm", -40, 40, 1, lambda v: f"{v:+.0f} mm")
        opt_slider("Gangguan", Y0 + 206, "Sudut awal", "init_angle_deg", -30, 30, 1, lambda v: f"{v:+.0f}°")
        hw = (pw - 6) // 2
        self.widgets["Gangguan"].append(Button((px, Y0 + 278, hw, 30), "Dorong ke samping", sim.push_side))
        self.widgets["Gangguan"].append(Button((px + hw + 6, Y0 + 278, hw, 30), "Putar 25°", sim.twist))
        check("Gangguan", Y0 + 324, "Kembalikan ke garis saat keluar lintasan", "auto_reset",
              "Matikan untuk aturan kompetisi: keluar = gagal, tekan R.")

    # ------------------------------------------------------------ aksi
    def toast(self, msg):
        self.toast_text, self.toast_time = msg, 2.0

    def toggle_pause(self):
        self.paused = not self.paused

    def reset(self):
        self.sim.reset()
        self.toast("Robot kembali ke garis start")

    def set_track(self, name):
        self.sim.set_track(name)
        self.fit_view()
        self.toast(f"Lintasan: {name} ({self.sim.track.length:.2f} m)")

    def set_sensors(self, n):
        self.opts.n_sensors = n
        self.sim.sensor_vals = [0.0] * n
        self.toast(f"{n} sensor")

    def apply_preset(self, name):
        self.sim.apply_preset(name)
        self.preset = name
        self.toast("Preset: " + name)

    def save_csv(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        path = os.path.join(DATA_DIR, datetime.now().strftime("line_follower_%Y%m%d_%H%M%S.csv"))
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["t", "e_mm", "u_pct", "P", "I", "D", "vL", "vR", "lateral_mm"])
            for row in self.sim.history:
                w.writerow([f"{v:.4f}" for v in row])
        self.toast(f"CSV disimpan: data/{os.path.basename(path)}")

    def save_screenshot(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        path = os.path.join(DATA_DIR, datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png"))
        pygame.image.save(self.screen, path)
        self.toast(f"Screenshot disimpan: data/{os.path.basename(path)}")

    # ------------------------------------------------------------ kamera
    def fit_view(self):
        x0, y0, x1, y1 = self.sim.track.bounds
        self.base_scale = min(SIM_RECT.w / (x1 - x0), (SIM_RECT.h - 30) / (y1 - y0)) * 0.97
        self.zoom = 1.0
        self.scale = self.base_scale
        self.cam_x, self.cam_y = (x0 + x1) / 2, (y0 + y1) / 2 - 12 / self.scale
        self.follow = False

    def set_zoom(self, z, anchor=None):
        z = max(0.5, min(25.0, z))
        anchor = anchor or SIM_RECT.center
        wx0, wy0 = self.screen_to_world(anchor)
        self.zoom = z
        self.scale = self.base_scale * z
        self.cam_x = wx0 - (anchor[0] - SIM_RECT.centerx) / self.scale
        self.cam_y = wy0 + (anchor[1] - SIM_RECT.centery) / self.scale

    def toggle_follow(self):
        self.follow = not self.follow
        if self.follow and self.zoom < 3:
            self.set_zoom(4)
        self.toast("Kamera mengikuti robot: " + ("ON" if self.follow else "OFF"))

    def update_camera(self, real_dt):
        if self.follow:
            a = min(1.0, real_dt * 6)
            self.cam_x += (self.sim.robot.x - self.cam_x) * a
            self.cam_y += (self.sim.robot.y - self.cam_y) * a

    def wx(self, x):
        return SIM_RECT.centerx + (x - self.cam_x) * self.scale

    def wy(self, y):
        return SIM_RECT.centery - (y - self.cam_y) * self.scale

    def screen_to_world(self, pos):
        return (self.cam_x + (pos[0] - SIM_RECT.centerx) / self.scale,
                self.cam_y - (pos[1] - SIM_RECT.centery) / self.scale)

    # ------------------------------------------------------------ events
    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                self.on_resize()
                continue
            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                d = dict(ev.dict)
                d["pos"] = gfx.to_logical(ev.pos)
                ev = pygame.event.Event(ev.type, d)
            if ev.type == pygame.KEYDOWN:
                k, o = ev.key, self.opts
                if k == pygame.K_SPACE:
                    self.toggle_pause()
                elif k == pygame.K_r:
                    self.reset()
                elif k == pygame.K_UP:
                    o.base_speed = min(100, o.base_speed + 5)
                elif k == pygame.K_DOWN:
                    o.base_speed = max(0, o.base_speed - 5)
                elif k == pygame.K_c:
                    self.save_csv()
                elif k == pygame.K_s:
                    self.save_screenshot()
                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.set_zoom(self.zoom * 1.25)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.set_zoom(self.zoom / 1.25)
                elif k in (pygame.K_0, pygame.K_KP0):
                    self.fit_view()
                elif k == pygame.K_f:
                    self.toggle_follow()
                elif k == pygame.K_F11:
                    self.toggle_fullscreen()
                elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    self.speed = {pygame.K_1: .25, pygame.K_2: .5, pygame.K_3: 1., pygame.K_4: 2.}[k]
                elif k == pygame.K_ESCAPE:
                    if self.fullscreen:
                        self.toggle_fullscreen()
                    else:
                        return False
                continue
            if ev.type == pygame.MOUSEWHEEL and SIM_RECT.collidepoint(gfx.mouse_pos()):
                self.set_zoom(self.zoom * (1.15 ** ev.y), anchor=gfx.mouse_pos())
                continue
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 2, 3) and SIM_RECT.collidepoint(ev.pos) \
                    and not any(b.rect.collidepoint(ev.pos) for b in self.sim_btns):
                self.panning = ev.pos
                self.follow = False
                continue
            if ev.type == pygame.MOUSEMOTION and self.panning:
                self.cam_x -= (ev.pos[0] - self.panning[0]) / self.scale
                self.cam_y += (ev.pos[1] - self.panning[1]) / self.scale
                self.panning = ev.pos
                continue
            if ev.type == pygame.MOUSEBUTTONUP and self.panning:
                self.panning = None
                continue
            for w in self.sim_btns + self.top + self.tabs + self.widgets[self.tab]:
                if w.handle(ev):
                    break
        return True

    # ------------------------------------------------------------ gambar
    def _sim_background(self):
        rr = gfx.R(SIM_RECT)
        if self._bg_cache is None or self._bg_cache.get_size() != rr.size:
            bg = pygame.Surface(rr.size)
            for i in range(rr.h):
                c = 15 + int(6 * i / rr.h)
                pygame.draw.line(bg, (c, c + 8, c + 21), (0, i), (rr.w, i))
            self._bg_cache = bg
        return self._bg_cache, rr.topleft

    def draw_sim(self):
        s, sim, r, tr = self.screen, self.sim, self.sim.robot, self.sim.track
        gfx.clip(s, SIM_RECT)
        bg, pos = self._sim_background()
        s.blit(bg, pos)

        # alas lintasan
        x0, y0, x1, y1 = tr.bounds
        mat = (self.wx(x0), self.wy(y1), (x1 - x0) * self.scale, (y1 - y0) * self.scale)
        gfx.rect(s, MAT, mat, border_radius=4)
        # garis
        step = max(1, int(2.5 / (DS * self.scale)))
        pts = [(self.wx(x), self.wy(y)) for x, y in tr.pts[::step]]
        lw = max(1.0, LINE_W * self.scale)
        gfx.lines(s, INK, True, pts, lw)
        # garis start/finish
        (sx, sy), (tx, ty) = tr.pts[0], tr.tan[0]
        nx, ny = -ty, tx
        for k in range(-3, 3):
            col = (220, 40, 40) if k % 2 else (250, 250, 250)
            a = (sx + nx * k * 0.015, sy + ny * k * 0.015)
            b = (sx + nx * (k + 1) * 0.015, sy + ny * (k + 1) * 0.015)
            gfx.line(s, col, (self.wx(a[0]), self.wy(a[1])), (self.wx(b[0]), self.wy(b[1])),
                     max(2.0, 0.012 * self.scale))
        if self.zoom <= 1.6:
            gfx.text(s, self.f_s, "START", (200, 40, 40),
                     midbottom=(self.wx(sx + nx * 0.07), self.wy(sy + ny * 0.07) - 2))

        # jejak
        trl = list(sim.trail)
        for i in range(1, len(trl)):
            f = i / len(trl)
            col = (int(228 - (228 - 40) * f), int(228 - (228 - 150) * f), int(222 - (222 - 230) * f))
            gfx.line(s, col, (self.wx(trl[i - 1][0]), self.wy(trl[i - 1][1])),
                     (self.wx(trl[i][0]), self.wy(trl[i][1])), 2)

        self.draw_robot(s)

        # HUD
        pl, pr = sim.pwm
        lap_txt = f"{sim.lap}" if sim.lap else "0"
        lines = [f"t     {sim.t:6.1f} s     lap {lap_txt}",
                 f"v     {r.v:6.2f} m/s",
                 f"e     {sim.e:+6.1f} mm",
                 f"PWM   L {pl:+5.0f}%  R {pr:+5.0f}%"]
        hw = max(gfx.text_size(self.f_m, ln)[0] for ln in lines) + 18
        gfx.alpha_rect(s, (13, 16, 21, 210), (SIM_RECT.x + 10, SIM_RECT.y + 10, hw, 17 * len(lines) + 12))
        for i, ln in enumerate(lines):
            gfx.text(s, self.f_m, ln, TXT, topleft=(SIM_RECT.x + 19, SIM_RECT.y + 16 + i * 17))
        text, kind = sim.status()
        if self.paused:
            text, kind = "DIJEDA", "warn"
        col = {"bad": BAD, "warn": SP, "mut": MUT, "ok": OK}[kind]
        tw, th = gfx.text_size(self.f_m, text)
        box = pygame.Rect(0, 0, tw + 16, th + 10)
        box.topright = (SIM_RECT.right - 10, SIM_RECT.y + 10)
        gfx.rect(s, BG, box, border_radius=5)
        gfx.rect(s, LINE, box, 1, border_radius=5)
        gfx.text(s, self.f_m, text, col, center=box.center)
        hint = "Roda: zoom · Seret: geser · F: ikuti robot · 0: tampilan penuh · ↑↓: kecepatan dasar"
        tw, th = gfx.text_size(self.f_s, hint)
        gfx.alpha_rect(s, (13, 16, 21, 190), (SIM_RECT.right - tw - 18, SIM_RECT.bottom - th - 10, tw + 12, th + 6))
        gfx.text(s, self.f_s, hint, MUT, bottomright=(SIM_RECT.right - 12, SIM_RECT.bottom - 6))
        gfx.clip(s, None)
        gfx.rect(s, LINE, SIM_RECT, 1, border_radius=6)

    def draw_robot(self, s):
        r, o, sim = self.sim.robot, self.opts, self.sim
        c, sn = math.cos(r.psi), math.sin(r.psi)

        def B(fx, ly):   # koordinat badan robot (maju, kiri) [m] -> layar
            return (self.wx(r.x + fx * c - ly * sn), self.wy(r.y + fx * sn + ly * c))

        def box(f0, f1, l0, l1, col):
            gfx.polygon(s, col, [B(f0, l0), B(f1, l0), B(f1, l1), B(f0, l1)])

        b = o.wheelbase_mm / 1000
        d = o.sensor_offset_mm / 1000
        half = (o.n_sensors - 1) / 2 * o.sensor_spacing_mm / 1000
        box(-0.045, 0.03, -(b / 2 - 0.01), b / 2 - 0.01, (45, 95, 170))              # badan
        box(0.02, max(0.021, d - 0.008), -0.012, 0.012, (35, 75, 140))                 # lengan
        box(d - 0.009, d + 0.009, -(half + 0.008), half + 0.008, (25, 105, 70))         # PCB sensor
        for side in (-1, 1):                                                            # roda
            box(-0.022, 0.022, side * b / 2 - 0.007, side * b / 2 + 0.007, (20, 20, 20))
        gfx.circle(s, (200, 200, 200), B(-0.035, 0), max(1.5, 0.006 * self.scale))   # roda bebas
        gfx.polygon(s, (240, 240, 240), [B(0.025, 0), B(0.005, 0.012), B(0.005, -0.012)])  # penanda depan
        rad = max(1.8, 0.0045 * self.scale)
        for (x, y), v in zip(sim.sensor_xy, sim.sensor_vals):
            col = (int(70 + 185 * v), int(70 - 30 * v), int(70 - 30 * v))
            gfx.circle(s, col, (self.wx(x), self.wy(y)), rad)

    @staticmethod
    def nice_step(x):
        p = 10 ** math.floor(math.log10(x))
        f = x / p
        return (1 if f < 1.5 else 2 if f < 3.5 else 5 if f < 7.5 else 10) * p

    def _plot_frame(self, rect, title, legend):
        s = self.screen
        gfx.rect(s, PANEL, rect, border_radius=8)
        gfx.rect(s, LINE, rect, 1, border_radius=8)
        x = rect.x + 10
        gfx.text(s, self.f_s, title, MUT, midleft=(x, rect.y + 13))
        x += gfx.text_size(self.f_s, title)[0] + 12
        for col, name in legend:
            gfx.line(s, col, (x, rect.y + 13), (x + 14, rect.y + 13), 2)
            gfx.text(s, self.f_s, name, MUT, midleft=(x + 18, rect.y + 13))
            x += gfx.text_size(self.f_s, name)[0] + 30

    def draw_plot(self, rect, title, legend, series, min_span):
        s = self.screen
        self._plot_frame(rect, title, legend)
        area = pygame.Rect(rect.x + 46, rect.y + 26, rect.w - 56, rect.h - 46)
        hist = self.sim.history
        vals = [h[i] for h in hist for i, _, _ in series] or [0.0]
        lo, hi = min(vals + [0.0]), max(vals + [0.0])
        mid = (lo + hi) / 2
        span = max(hi - lo, min_span) * 1.15
        lo, hi = mid - span / 2, mid + span / 2
        t1 = max(self.sim.t, PLOT_WINDOW)
        t0 = t1 - PLOT_WINDOW

        def X(tv):
            return area.x + (tv - t0) / PLOT_WINDOW * area.w

        def Y(v):
            return area.y + (hi - v) / (hi - lo) * area.h

        st = self.nice_step(span / 4)
        v = math.ceil(lo / st) * st
        while v <= hi:
            yy = Y(v)
            gfx.line(s, (60, 68, 88) if abs(v) < 1e-9 else (32, 38, 52), (area.x, yy), (area.right, yy))
            gfx.text(s, self.f_s, f"{v:g}", MUT, midright=(area.x - 5, yy))
            v += st
        tv = math.ceil(t0 / 2) * 2
        while tv <= t1:
            xx = X(tv)
            gfx.line(s, (32, 38, 52), (xx, area.y), (xx, area.bottom))
            gfx.text(s, self.f_s, f"{tv:g}s", MUT, midtop=(xx, area.bottom + 3))
            tv += 2
        gfx.clip(s, area)
        for idx, col, width in series:
            if len(hist) >= 2:
                gfx.lines(s, col, False, [(X(h[0]), Y(h[idx])) for h in hist], width)
        gfx.clip(s, None)

    def draw_sensor_plot(self, rect):
        s, sim, o = self.screen, self.sim, self.opts
        self._plot_frame(rect, f"Pembacaan sensor ({o.n_sensors})", [(SP, "posisi garis e")])
        area = pygame.Rect(rect.x + 46, rect.y + 28, rect.w - 56, rect.h - 52)
        vals = sim.sensor_vals or [0.0] * o.n_sensors
        n = len(vals)
        for frac, lab in ((0, "0"), (0.5, "0.5"), (1, "1")):
            yy = area.bottom - frac * area.h
            gfx.line(s, (32, 38, 52), (area.x, yy), (area.right, yy))
            gfx.text(s, self.f_s, lab, MUT, midright=(area.x - 5, yy))
        cw = area.w / n
        for i, v in enumerate(vals):
            h = v * area.h
            col = (int(70 + 185 * v), int(80 - 30 * v), int(90 - 40 * v))
            gfx.rect(s, col, (area.x + i * cw + cw * 0.15, area.bottom - h, cw * 0.7, max(1, h)), border_radius=2)
            if n <= 8 or i % 2 == 0:
                gfx.text(s, self.f_xs, str(i), MUT, midtop=(area.x + (i + 0.5) * cw, area.bottom + 3))
        # posisi garis: e positif = garis di kiri (sensor indeks kecil)
        i_eq = (n - 1) / 2 - sim.e / o.sensor_spacing_mm      # indeks sensor setara posisi garis
        xx = area.x + max(0.0, min(n, i_eq + 0.5)) * cw
        gfx.line(s, SP, (xx, area.y - 2), (xx, area.bottom), 2)
        label = f"e = {sim.e:+.1f} mm" + ("" if sim.line_seen else "  (garis hilang!)")
        gfx.text(s, self.f_s, label, SP if sim.line_seen else BAD, midright=(rect.right - 10, rect.y + 13))

    @staticmethod
    def fmt_t(v):
        return "—" if v is None else f"{v:.2f} s"

    def draw_metrics(self):
        s, sim = self.screen, self.sim
        last_speed = sim.track.length / sim.last_lap if sim.last_lap else None
        boxes = (
            ("Waktu lap", [("Lap selesai", f"{sim.lap}"),
                           ("Lap sekarang", self.fmt_t(sim.current_lap_time())),
                           ("Lap terakhir", self.fmt_t(sim.last_lap)),
                           ("Lap terbaik", self.fmt_t(sim.best_lap))]),
            ("Kualitas lintasan (lap ini)", [("RMS lateral", f"{sim.lap_rms_mm():.1f} mm"),
                                             ("Maks lateral", f"{sim.max_lat * 1000:.1f} mm"),
                                             ("Kec. rata-rata", "—" if last_speed is None else f"{last_speed:.2f} m/s"),
                                             ("Keluar lintasan", f"{sim.off_count}×")]),
        )
        for i, (title, items) in enumerate(boxes):
            r = pygame.Rect(10 + i * 425, 458, 415, 54)
            gfx.rect(s, PANEL, r, border_radius=8)
            gfx.rect(s, LINE, r, 1, border_radius=8)
            gfx.text(s, self.f_s, title, MUT, topleft=(r.x + 10, r.y + 4))
            cw = (r.w - 20) / 4
            for j, (lab, val) in enumerate(items):
                cx = r.x + 10 + j * cw
                gfx.text(s, self.f_s, lab, MUT, topleft=(cx, r.y + 20))
                col = BAD if (lab == "Keluar lintasan" and sim.off_count) else TXT
                gfx.text(s, self.f_mb, val, col, topleft=(cx, r.y + 33))

    def draw_panel(self):
        s = self.screen
        gfx.rect(s, PANEL, PANEL_RECT, border_radius=8)
        gfx.rect(s, LINE, PANEL_RECT, 1, border_radius=8)
        gfx.line(s, LINE, (PANEL_RECT.x, PANEL_RECT.y + 40), (PANEL_RECT.right - 1, PANEL_RECT.y + 40))
        for b in self.tabs:
            b.draw(s, self.f)
        px, Y0 = PANEL_RECT.x + 10, PANEL_RECT.y

        if self.tab == "PID":
            gfx.text(s, self.f_s, "PRESET (Kp, Ki, Kd, kecepatan dasar)", MUT, topleft=(px, Y0 + 46))
            box, pid = self.pid_box, self.sim.pid
            gfx.rect(s, PANEL2, box, border_radius=8)
            gfx.rect(s, LINE, box, 1, border_radius=8)
            gfx.text(s, self.f, "PID posisi garis", TXT, topleft=(box.x + 10, box.y + 7))
            gfx.text(s, self.f_s, "e [mm] → u [% PWM]:  kiri = dasar − u,  kanan = dasar + u", MUT,
                     topleft=(box.x + 10, box.y + 27))
            lim = 100.0
            vals = (("P", pid.p, COL_P), ("I", pid.integral, COL_I), ("D", pid.d, COL_D),
                    ("u", max(pid.out_min, min(pid.out_max, pid.u)), TXT))
            cw = (box.w - 20) / 4
            for j, (n, v, col) in enumerate(vals):
                cx = box.x + 10 + j * cw
                gfx.text(s, self.f_s, f"{n}: {v:+.1f}", MUT, topleft=(cx, box.y + 121))
                tr = pygame.Rect(cx, box.y + 139, cw - 8, 5)
                gfx.rect(s, BG, tr, border_radius=2)
                rr = max(-1, min(1, v / lim))
                w = abs(rr) * tr.w / 2
                mid = tr.centerx
                if w >= 0.5:
                    gfx.rect(s, col, (mid if rr > 0 else mid - w, tr.y, w, tr.h), border_radius=2)
                gfx.line(s, LINE, (mid, tr.y), (mid, tr.bottom))
        elif self.tab == "Robot":
            gfx.text(s, self.f_s, "SENSOR", MUT, topleft=(px, Y0 + 48))
            gfx.text(s, self.f, "Jumlah sensor", MUT, midleft=(px, Y0 + 79))
            gfx.text(s, self.f_s, "PENGGERAK", MUT, topleft=(px, Y0 + 184))
            gfx.text(s, self.f_s, f"Lebar garis {LINE_W * 1000:.0f} mm · lebar array "
                     f"{(self.opts.n_sensors - 1) * self.opts.sensor_spacing_mm:.0f} mm", MUT,
                     topleft=(px, Y0 + 164))
        elif self.tab == "Gangguan":
            gfx.text(s, self.f_s, "SENSOR & MOTOR", MUT, topleft=(px, Y0 + 48))
            gfx.text(s, self.f_s, "POSISI AWAL (berlaku saat Reset)", MUT, topleft=(px, Y0 + 150))
            gfx.text(s, self.f_s, "GANGGUAN SESAAT", MUT, topleft=(px, Y0 + 256))
            self.wrap(["Motor kiri yang lebih lemah membuat robot selalu sedikit",
                       "melenceng; perhatikan peran Ki untuk menghilangkannya."], px, Y0 + 400)
        elif self.tab == "Bantuan":
            self.wrap([
                "CARA KERJA",
                "  Sensor membaca garis (0 = putih, 1 = hitam). Posisi garis:",
                "  e = Σ(vᵢ·yᵢ) / Σvᵢ   [mm, positif = garis di kiri]",
                "  u = Kp·e + Ki·∫e dt + Kd·de/dt",
                "  PWM kiri = dasar − u,   PWM kanan = dasar + u",
                "",
                "MODEL ROBOT (differential drive)",
                "  v = (vL + vR)/2,   ω = (vR − vL)/b",
                "  motor orde-1; ban tergelincir bila |v·ω| > μ·g",
                "",
                "ATURAN",
                "  Keluar lintasan: >10 cm dari garis, garis hilang >1 s,",
                "  atau robot berbalik arah.",
                "",
                "SARAN PERCOBAAN",
                "1. Preset 'Hanya P' di lintasan Siku: amati osilasi & robot",
                "    berbalik arah. Naikkan Kd sampai mulus.",
                "2. Cari kecepatan dasar tertinggi tanpa keluar lintasan.",
                "    Bandingkan dengan 'Kurangi kecepatan di tikungan'.",
                "3. Efisiensi motor kiri 70%: bandingkan PD vs PID (Ki).",
                "4. Ubah jarak sensor ke roda 20 mm vs 120 mm.",
                "5. Bandingkan 5, 8, dan 16 sensor di lintasan Gelombang.",
                "6. Turunkan frekuensi kendali ke 50 Hz pada kecepatan tinggi.",
                "",
                "PINTASAN",
                "  Spasi jeda · R reset · ↑↓ kecepatan dasar · 1–4 kec. simulasi",
                "  C simpan CSV · S screenshot · F11 layar penuh",
            ], px, Y0 + 50)

        for x, y, note in self.notes[self.tab]:
            gfx.text(s, self.f_s, note, MUT, topleft=(x, y + 1))
        for w in self.widgets[self.tab]:
            if isinstance(w, Button):
                w.draw(s, self.f_xs if getattr(w, "small", False) else self.f_s)
            else:
                w.draw(s, self.f)

    def wrap(self, lines, x, y):
        for ln in lines:
            col = ACC if (ln.isupper() and ln.strip()) else TXT
            gfx.text(self.screen, self.f_s, ln, col, topleft=(x, y))
            y += 19

    def draw(self, real_dt):
        s = self.screen
        s.fill(BG)
        gfx.text(s, self.f_title, "Simulasi PID Line Follower", TXT, topleft=(12, 5))
        gfx.text(s, self.f_s, "Robot differential drive · sensor array · kompetisi", MUT, topleft=(12, 28))
        gfx.line(s, LINE, (0, 46), (WIN_W, 46))
        for b in self.top:
            b.draw(s, self.f_s)
        self.update_camera(real_dt)
        self.draw_sim()
        for b in self.sim_btns:
            b.draw(s, self.f)
        gfx.text(s, self.f_s, f"Zoom {self.zoom * 100:.0f}%", MUT,
                 midleft=(self.sim_btns[-1].rect.right + 10, self.sim_btns[-1].rect.centery))
        self.draw_metrics()
        pw, ph = 415, 134
        self.draw_plot(pygame.Rect(10, 518, pw, ph), "Error posisi garis (mm)", [(ACC, "e")],
                       [(1, ACC, 2)], 10)
        self.draw_plot(pygame.Rect(435, 518, pw, ph), "Keluaran PID (% PWM)",
                       [(COL_P, "P"), (COL_I, "I"), (COL_D, "D"), (TXT, "u")],
                       [(3, COL_P, 1), (4, COL_I, 1), (5, COL_D, 1), (2, TXT, 2)], 10)
        self.draw_plot(pygame.Rect(10, 658, pw, ph), "Kecepatan roda (m/s)", [(M1, "kiri"), (M2, "kanan")],
                       [(6, M1, 2), (7, M2, 2)], 0.5)
        self.draw_sensor_plot(pygame.Rect(435, 658, pw, ph))
        self.draw_panel()
        if self.toast_time > 0:
            self.toast_time -= real_dt
            tw, th = gfx.text_size(self.f, self.toast_text)
            box = pygame.Rect(0, 0, tw + 24, th + 14)
            box.midbottom = (WIN_W // 2, WIN_H - 14)
            gfx.rect(s, PANEL2, box, border_radius=8)
            gfx.rect(s, ACC, box, 1, border_radius=8)
            gfx.text(s, self.f, self.toast_text, TXT, center=box.center)

    # ------------------------------------------------------------ loop
    def run(self):
        running = True
        while running:
            real_dt = min(self.clock.tick(60) / 1000.0, 0.05)
            running = self.handle_events()
            if not self.paused:
                self.sim.advance(real_dt, self.speed)
            self.draw(real_dt)
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    App().run()
    sys.exit(0)
