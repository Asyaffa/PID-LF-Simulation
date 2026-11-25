"""Simulasi line follower: sensor array + PID + robot + pencatat lap."""
import math
import random
from collections import deque

from config import DT_PHYS, PLOT_WINDOW
from pid import PID
from robot import Robot
from track import Track

# Preset (Kp, Ki, Kd, kecepatan dasar %)
PRESETS = {
    "Seimbang": (2.0, 0.0, 0.05, 50),
    "Hanya P":  (2.0, 0.0, 0.0, 50),
    "PD cepat": (3.0, 0.0, 0.08, 70),
    "PID":      (2.0, 3.0, 0.05, 50),
    "Lambat":   (1.2, 0.0, 0.03, 35),
}


class Simulation:
    def __init__(self, opts, track_name="Oval"):
        self.opts = opts
        self.robot = Robot()
        # e [mm] -> u [% PWM selisih kiri/kanan]
        self.pid = PID(2.0, 0.0, 0.05, -200, 200)
        self.history = deque()   # (t, e, u, P, I, D, vL, vR, lat_mm)
        self.trail = deque(maxlen=90)
        self.set_track(track_name)

    # ------------------------------------------------------------------
    def set_track(self, name):
        self.track = Track(name)
        self.reset()

    def reset(self):
        o = self.opts
        x, y, psi = self.track.start_pose()
        off = o.init_offset_mm / 1000
        x -= math.sin(psi) * off
        y += math.cos(psi) * off
        self.robot.reset(x, y, psi + math.radians(o.init_angle_deg))
        self.pid.reset()
        self.t = 0.0
        self.ctrl_acc = 1.0
        self.sample_acc = self.trail_acc = self.time_acc = 0.0
        self.sensor_vals = [0.0] * o.n_sensors
        self.sensor_xy = []
        self.e = 0.0
        self.last_pos = 0.0
        self.line_seen = True
        self.lost_time = 0.0
        self.pwm = (0.0, 0.0)
        self.u = 0.0
        self.idx, self.lat = self.track.nearest(self.robot.x, self.robot.y)
        self.off_track = False
        self.reversed = False
        self.off_count = 0
        # statistik lap
        self.lap = 0
        self.lap_start = 0.0
        self.last_lap = None
        self.best_lap = None
        self.last_lap_rms = None
        self.sum_sq = 0.0
        self.n_sq = 0
        self.max_lat = 0.0
        self.history.clear()
        self.trail.clear()

    def apply_preset(self, name):
        kp, ki, kd, base = PRESETS[name]
        self.pid.kp, self.pid.ki, self.pid.kd = kp, ki, kd
        self.pid.integral = 0.0
        self.opts.base_speed = base

    def push_side(self):
        r = self.robot
        d = random.choice((-1, 1)) * 0.025
        r.x -= math.sin(r.psi) * d
        r.y += math.cos(r.psi) * d

    def twist(self):
        self.robot.psi += random.choice((-1, 1)) * math.radians(25)

    # ------------------------------------------------------------------
    def read_sensors(self):
        o, r = self.opts, self.robot
        n = o.n_sensors
        sp = o.sensor_spacing_mm / 1000
        d = o.sensor_offset_mm / 1000
        c, s = math.cos(r.psi), math.sin(r.psi)
        vals, xy, lys = [], [], []
        for i in range(n):
            ly = ((n - 1) / 2 - i) * sp          # i = 0 sensor paling kiri
            sx = r.x + d * c - ly * s
            sy = r.y + d * s + ly * c
            v = self.track.coverage(sx, sy)
            if o.sensor_noise > 0:
                v += random.gauss(0, o.sensor_noise)
            vals.append(min(1.0, max(0.0, v)))
            xy.append((sx, sy))
            lys.append(ly)
        return vals, xy, lys

    def control(self, dt):
        o = self.opts
        vals, xy, lys = self.read_sensors()
        self.sensor_vals, self.sensor_xy = vals, xy
        half = (o.n_sensors - 1) / 2 * o.sensor_spacing_mm
        total = sum(vals)
        if total > 0.3:
            # posisi garis = rata-rata berbobot posisi sensor [mm]
            pos = sum(v * ly for v, ly in zip(vals, lys)) / total * 1000
            self.line_seen = True
            self.lost_time = 0.0
            self.last_pos = pos
        else:
            self.line_seen = False
            self.lost_time += dt
            if o.line_memory:
                pos = half if self.last_pos > 0 else -half
            else:
                pos = 0.0
        self.e = pos

        u = self.pid.update(0.0, -pos, dt, o)   # e = 0 - (-pos) = pos
        self.u = u
        base = o.base_speed
        if o.curve_slowdown:
            base *= 1 - o.slowdown_k * min(1.0, abs(pos) / half)
        lo = -100.0 if o.allow_reverse else 0.0
        pl = max(lo, min(100.0, base - u))
        pr = max(lo, min(100.0, base + u))
        self.pwm = (pl, pr)

    def step(self, h):
        o, r = self.opts, self.robot
        self.t += h
        self.ctrl_acc += h
        if self.ctrl_acc >= 1.0 / o.control_hz - 1e-9:
            self.control(self.ctrl_acc)
            self.ctrl_acc = 0.0
        pl, pr = self.pwm
        r.step(pl / 100 * o.vmax * o.motor_left_eff, pr / 100 * o.vmax,
               o.wheelbase_mm / 1000, o.tau_motor, o.mu, h)

        self.sample_acc += h
        if self.sample_acc >= 1 / 60:
            self.sample_acc = 0.0
            self._sample()
        self.trail_acc += h
        if self.trail_acc >= 1 / 30:
            self.trail_acc = 0.0
            self.trail.append((r.x, r.y))

    def _sample(self):
        r, tr = self.robot, self.track
        prev = self.idx
        self.idx, self.lat = tr.nearest(r.x, r.y, hint=self.idx)
        n = tr.n
        # deteksi lap: indeks melewati titik start (maju)
        if prev > 0.85 * n and self.idx < 0.15 * n:
            lap_time = self.t - self.lap_start
            self.lap += 1
            self.last_lap = lap_time
            if self.best_lap is None or lap_time < self.best_lap:
                self.best_lap = lap_time
            self.last_lap_rms = math.sqrt(self.sum_sq / max(1, self.n_sq)) * 1000
            self.lap_start = self.t
            self.sum_sq, self.n_sq, self.max_lat = 0.0, 0, 0.0
        self.sum_sq += self.lat ** 2
        self.n_sq += 1
        self.max_lat = max(self.max_lat, abs(self.lat))

        # keluar lintasan: terlalu jauh dari garis, garis hilang > 1 s,
        # atau robot berbalik arah (melawan arah lomba)
        tx, ty = tr.tan[self.idx]
        self.reversed = tx * math.cos(r.psi) + ty * math.sin(r.psi) < -0.3 and abs(r.v) > 0.05
        out = abs(self.lat) > 0.10 or self.lost_time > 1.0 or self.reversed
        if out and not self.off_track:
            self.off_count += 1
            self.off_track = True
            if self.opts.auto_reset:
                (x, y), (tx, ty) = tr.pts[self.idx], tr.tan[self.idx]
                r.reset(x, y, math.atan2(ty, tx))
                r.odometer = 0.0
                self.pid.reset()
                self.lost_time = 0.0
                self.last_pos = 0.0
                self.lat = 0.0
        elif not out:
            self.off_track = False

        P, I, D = self.pid.p, self.pid.integral, self.pid.d
        self.history.append((self.t, self.e, self.u, P, I, D, r.vL, r.vR, self.lat * 1000))
        while self.history and self.history[0][0] < self.t - PLOT_WINDOW:
            self.history.popleft()

    def advance(self, real_dt, speed):
        self.time_acc += real_dt * speed
        n = 0
        while self.time_acc >= DT_PHYS and n < 300:
            self.step(DT_PHYS)
            self.time_acc -= DT_PHYS
            n += 1
        if n >= 300:
            self.time_acc = 0.0

    # ------------------------------------------------------------------
    def current_lap_time(self):
        return self.t - self.lap_start

    def lap_rms_mm(self):
        return math.sqrt(self.sum_sq / max(1, self.n_sq)) * 1000

    def status(self):
        if self.off_track and not self.opts.auto_reset:
            return ("BERBALIK ARAH - tekan R" if self.reversed else "KELUAR LINTASAN - tekan R"), "bad"
        if not self.line_seen:
            return "Garis hilang", "warn"
        if self.robot.slip:
            return "Ban tergelincir", "warn"
        return "Mengikuti garis", "ok"
