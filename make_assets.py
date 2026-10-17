"""Generate icon.png / icon.ico / logo.png (a neon ghost). Run: python gui/assets/make_assets.py"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
BG, GREEN = (10, 10, 15, 255), (0, 255, 156, 255)


def ghost(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 512
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(110 * s), fill=BG, outline=(0, 212, 255, 255), width=max(2, int(6 * s)))
    x0, x1, top, bottom = 126 * s, 386 * s, 96 * s, 410 * s
    d.ellipse((x0, top, x1, top + (x1 - x0)), fill=GREEN)                      # head
    d.rectangle((x0, top + (x1 - x0) / 2, x1, bottom), fill=GREEN)            # body
    r = (x1 - x0) / 6
    for i in range(3):                                                         # wavy hem
        cx = x0 + r + i * 2 * r * 1.0
        d.ellipse((cx - r + r, bottom - r, cx + r + r, bottom + r), fill=BG)
    for ex in (205 * s, 307 * s):                                              # eyes
        d.ellipse((ex - 22 * s, 205 * s, ex + 22 * s, 255 * s), fill=BG)
    return img


if __name__ == "__main__":
    g = ghost()
    g.save(OUT / "logo.png")
    g.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    g.save(OUT / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("assets written to", OUT)
