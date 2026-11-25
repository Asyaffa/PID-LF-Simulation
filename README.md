# Simulasi PID Robot Line Follower

Simulator real-time robot line follower (differential drive) dengan array sensor garis dan pengendali PID. Dibuat untuk praktikum/demonstrasi mata kuliah Teknik Kendali dan persiapan kompetisi robot.

## Isi folder

```
line-follower-sim/
├── main.py          # aplikasi utama (antarmuka pygame) — jalankan file ini
├── sim.py           # simulasi: pembacaan sensor, PID, aturan lomba, pencatat lap
├── robot.py         # model robot differential drive (motor orde-1, batas traksi)
├── track.py         # lintasan: Oval, Angka 8, Siku, Gelombang
├── pid.py           # kelas PID diskrit (filter D, anti-windup)
├── config.py        # konstanta & opsi simulasi
├── gfx.py           # lapisan gambar skala-bebas (tajam di semua resolusi)
├── ui.py            # widget tombol, slider, checkbox
├── fonts.py         # pemuatan font
├── requirements.txt
├── data/            # hasil CSV & screenshot disimpan di sini
└── .vscode/         # konfigurasi Run/Debug VS Code
```

## Menjalankan di VS Code

1. Pasang **Python 3.10+** dan ekstensi **Python** di VS Code.
2. Buka folder ini: *File → Open Folder…*
3. Di terminal VS Code:

   **Windows**
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   **macOS / Linux**
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   > Proyek ini memakai **pygame-ce** (mendukung Python 3.10–3.14). Kode tetap memakai `import pygame`. Jika `pygame` biasa sudah terpasang, hapus dulu dengan `pip uninstall pygame`.
4. Pilih interpreter `.venv` (*Ctrl+Shift+P → Python: Select Interpreter*).
5. Tekan **F5**, atau jalankan `python main.py`.

## Kontrol

| Aksi | Cara |
|---|---|
| Pilih lintasan | tombol Oval / Angka 8 / Siku / Gelombang |
| Jeda / lanjut | Spasi |
| Reset ke garis start | R |
| Kecepatan dasar ±5% | Panah atas / bawah |
| Kecepatan simulasi 0,25× / 0,5× / 1× / 2× | 1 / 2 / 3 / 4 |
| Zoom | roda mouse di area lintasan, tombol − / + / Pas, atau + − 0 |
| Geser tampilan | seret dengan mouse di area lintasan |
| Kamera mengikuti robot | F atau tombol *Ikuti* |
| Simpan data (CSV) / screenshot | C / S (folder `data/`) |
| Layar penuh | F11 (Esc untuk keluar) |
| Penyesuaian halus slider | roda mouse di atas slider |

## Model

**Sensor.** Setiap sensor membaca bidang kecil di permukaan (0 = putih, 1 = hitam). Garis hitam selebar 19 mm. Posisi garis dihitung sebagai rata-rata berbobot:

```
e = Σ(vᵢ · yᵢ) / Σvᵢ      [mm, positif = garis di kiri robot]
```

Jika semua sensor tidak melihat garis, robot memakai arah terakhir garis (opsi *Ingat arah garis*).

**Pengendali.**

```
u = Kp·e + Ki·∫e dt + Kd·de/dt          [% PWM]
PWM kiri  = dasar − u
PWM kanan = dasar + u
```

**Robot (differential drive).**

```
v = (vL + vR)/2,   ω = (vR − vL)/b
x' = v·cos ψ,   y' = v·sin ψ,   ψ' = ω
```

Motor dimodelkan orde-1. Jika |v·ω| > μ·g, ban tergelincir dan robot tidak mampu menikung setajam perintah. Fisika diintegrasikan pada 1 kHz; pengendali berjalan pada frekuensi yang bisa diatur (default 500 Hz).

**Aturan lomba.** Robot dianggap keluar lintasan bila berjarak lebih dari 10 cm dari garis, garis hilang lebih dari 1 detik, atau robot berbalik arah. Waktu lap dicatat setiap kali robot melewati garis START.

## Saran percobaan

1. Preset *Hanya P* di lintasan Siku: amati osilasi dan robot berbalik arah. Naikkan Kd sampai gerakannya mulus.
2. Cari kecepatan dasar tertinggi tanpa keluar lintasan. Bandingkan dengan opsi *Kurangi kecepatan di tikungan*.
3. Atur efisiensi motor kiri ke 70% (tab Gangguan). Bandingkan PD dengan PID (Ki > 0).
4. Bandingkan jarak sensor ke roda 20 mm dan 120 mm.
5. Bandingkan 5, 8, dan 16 sensor di lintasan Gelombang.
6. Turunkan frekuensi kendali ke 50 Hz pada kecepatan tinggi.

Kolom CSV: `t, e_mm, u_pct, P, I, D, vL, vR, lateral_mm`.
