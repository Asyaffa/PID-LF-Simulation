"""Model kinematika robot differential drive dengan dinamika motor dan batas traksi.

    v = (vL + vR) / 2           kecepatan maju
    w = (vR - vL) / b           kecepatan sudut (b = jarak antar roda)
    x' = v cos(psi),  y' = v sin(psi),  psi' = w

Motor dimodelkan orde-1 (konstanta waktu tau). Jika percepatan sentripetal
|v*w| melebihi mu*g, ban tergelincir sehingga robot tidak mampu berbelok
setajam yang diperintahkan (understeer).
"""
import math
from config import G


class Robot:
    def __init__(self):
        self.reset(0, 0, 0)

    def reset(self, x, y, psi):
        self.x, self.y, self.psi = x, y, psi
        self.vL = self.vR = 0.0
        self.v = self.w = 0.0
        self.slip = False
        self.odometer = 0.0

    def step(self, cmd_l, cmd_r, wheelbase, tau, mu, h):
        self.vL += (cmd_l - self.vL) * h / tau
        self.vR += (cmd_r - self.vR) * h / tau
        v = 0.5 * (self.vL + self.vR)
        w = (self.vR - self.vL) / wheelbase
        lim = mu * G / max(abs(v), 1e-3)
        self.slip = abs(w) > lim
        w = max(-lim, min(lim, w))
        self.x += v * math.cos(self.psi) * h
        self.y += v * math.sin(self.psi) * h
        self.psi = (self.psi + w * h + math.pi) % (2 * math.pi) - math.pi
        self.v, self.w = v, w
        self.odometer += abs(v) * h
