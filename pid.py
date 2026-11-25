"""Implementasi pengendali PID diskrit.

    u[k] = Kp*e[k] + Ki*Ts*sum(e) + Kd*(de/dt, difilter)

Fitur:
- turunan pada pengukuran (menghindari derivative kick)
- filter low-pass orde-1 pada suku D
- anti-windup dengan integrasi bersyarat (clamping)
"""
import math


class PID:
    def __init__(self, kp, ki, kd, out_min, out_max):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.out_min, self.out_max = out_min, out_max
        self.enabled = True
        self.reset()

    def reset(self):
        self.integral = 0.0
        self.d_filt = 0.0
        self.prev_err = 0.0
        self.prev_meas = 0.0
        self.first = True
        # kontribusi tiap suku (untuk ditampilkan)
        self.p = self.d = self.u = 0.0

    def update(self, setpoint, measurement, dt, opts):
        err = setpoint - measurement

        # --- Proporsional ---
        p = self.kp * err

        # --- Derivatif (dengan filter) ---
        if self.first:
            d_raw = 0.0
            self.first = False
        elif opts.d_on_measurement:
            d_raw = -(measurement - self.prev_meas) / dt
        else:
            d_raw = (err - self.prev_err) / dt
        if opts.d_cutoff_hz >= 200:
            alpha = 1.0
        else:
            alpha = dt / (dt + 1.0 / (2 * math.pi * opts.d_cutoff_hz))
        self.d_filt += alpha * (d_raw - self.d_filt)
        d = self.kd * self.d_filt

        # --- Integral (dengan anti-windup) ---
        i_new = self.integral + self.ki * err * dt
        if opts.anti_windup:
            u_try = p + i_new + d
            if (u_try > self.out_max and err > 0) or (u_try < self.out_min and err < 0):
                i_new = self.integral          # hentikan integrasi saat saturasi
            i_new = max(self.out_min, min(self.out_max, i_new))
        self.integral = i_new

        self.p, self.d = p, d
        self.u = p + self.integral + d
        self.prev_err, self.prev_meas = err, measurement
        return max(self.out_min, min(self.out_max, self.u))
