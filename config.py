"""Konstanta dan opsi simulasi robot line follower."""
from dataclasses import dataclass

G = 9.81
LINE_W = 0.019        # lebar garis hitam [m] (standar kompetisi 18-20 mm)
DT_PHYS = 0.001       # langkah fisika 1 kHz
PLOT_WINDOW = 8.0     # panjang jendela grafik [s]


@dataclass
class SimOptions:
    # --- PID & strategi ---
    base_speed: float = 50.0        # kecepatan dasar [% PWM]
    curve_slowdown: bool = False     # kurangi kecepatan saat error besar
    slowdown_k: float = 0.4         # besar pengurangan (0..0.9)
    line_memory: bool = True        # ingat arah terakhir saat garis hilang
    anti_windup: bool = True
    d_on_measurement: bool = True   # (setpoint selalu 0, tidak berpengaruh)
    d_cutoff_hz: float = 50.0       # filter turunan [Hz] (>=200 = tanpa filter)
    control_hz: float = 500.0       # frekuensi loop kendali [Hz]
    # --- robot ---
    n_sensors: int = 8
    sensor_spacing_mm: float = 14.0
    sensor_offset_mm: float = 50.0  # jarak array sensor di depan sumbu roda
    wheelbase_mm: float = 140.0
    vmax: float = 2.5               # kecepatan roda pada PWM 100% [m/s]
    tau_motor: float = 0.05         # konstanta waktu motor [s]
    mu: float = 1.0                 # koefisien gesek ban (batas traksi)
    allow_reverse: bool = True      # PWM negatif diizinkan
    # --- gangguan ---
    sensor_noise: float = 0.0       # std noise pembacaan sensor (0..1)
    motor_left_eff: float = 1.0     # efisiensi motor kiri relatif kanan
    init_offset_mm: float = 0.0     # offset lateral saat reset
    init_angle_deg: float = 0.0     # sudut awal saat reset
    auto_reset: bool = True         # kembalikan robot ke garis saat keluar
