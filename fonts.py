"""Pemuatan font yang tahan galat (termasuk Python 3.14 di Windows)."""
import os
import pygame

FONT_NAMES = {"sans": "segoeui,dejavusans,arial,helvetica",
              "mono": "consolas,dejavusansmono,menlo,couriernew"}
FONT_FILES = {
    "sans": [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
             "/System/Library/Fonts/Supplemental/Arial.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "mono": [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf",
             "/System/Library/Fonts/Menlo.ttc",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
}
FONT_BOLD_FILES = {
    "sans": [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "mono": [r"C:\Windows\Fonts\consolab.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"],
}


def load_font(kind, size, bold=False):
    """Muat font pada ukuran piksel `size`: file font asli dulu, lalu SysFont,
    lalu font bawaan pygame."""
    for path in (FONT_BOLD_FILES[kind] if bold else []) + FONT_FILES[kind]:
        if os.path.exists(path):
            try:
                f = pygame.font.Font(path, size)
                if bold and path not in FONT_BOLD_FILES[kind]:
                    f.set_bold(True)
                return f
            except Exception:
                continue
    try:
        return pygame.font.SysFont(FONT_NAMES[kind], size, bold=bold)
    except Exception:
        f = pygame.font.Font(None, int(size * 1.3))
        f.set_bold(bold)
        return f
