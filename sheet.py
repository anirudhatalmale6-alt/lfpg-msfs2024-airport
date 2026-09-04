import sys
from PIL import Image, ImageDraw, ImageFont

PANELS = [
    ('v1_overview.png', 'The whole aerodrome from the south'),
    ('c_lineup.png',    'Lined up on runway 27R, looking down the centreline'),
    ('v3_t1.png',       'Terminal 1 and Satellite U'),
    ('v4_t2e.png',      'Terminal 2 piers, 08L/26R in the foreground'),
]
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 21)
GAP, TOP = 6, 44

ims = [Image.open(p) for p, _ in PANELS]
w, h = ims[0].size
W = w * 2 + GAP
H = TOP + h * 2 + GAP
sheet = Image.new('RGB', (W, H), (24, 26, 30))
d = ImageDraw.Draw(sheet)
d.text((14, 12), 'LFPG  PARIS CHARLES DE GAULLE   built to scale from survey data, '
                 'rendered here - not yet in the sim', font=FB, fill=(238, 238, 234))

for i, (im, (_, cap)) in enumerate(zip(ims, PANELS)):
    x = (i % 2) * (w + GAP)
    y = TOP + (i // 2) * (h + GAP)
    sheet.paste(im, (x, y))
    bar = Image.new('RGBA', (w, 34), (16, 18, 22, 205))
    sheet.paste(bar, (x, y + h - 34), bar)
    d.text((x + 12, y + h - 28), cap, font=FB, fill=(240, 240, 236))

out = sys.argv[1] if len(sys.argv) > 1 else 'lfpg_3d_sheet.jpg'
sheet.save(out, quality=90)
print(out, sheet.size)
