"""Draw the header lockup for The Creation Foundation.

Same 1367x150 canvas as the old Launchpad lockup so the <img> width/height and
srcset stay valid: a heavy wordmark, a hairline divider, and a lighter second
line, all in Plus Jakarta Sans (the site's own font).
"""
from PIL import Image, ImageDraw, ImageFont

FONT = '_next/static/les/media/fba5a26ea33df6a3-s.p.08ssgmy_tb90r.woff2'
W, H, SS = 1367, 150, 4  # supersample for clean edges


def font(size, weight):
    f = ImageFont.truetype(FONT, size * SS)
    f.set_variation_by_axes([weight])
    return f


img = Image.new('L', (W * SS, H * SS), 0)
d = ImageDraw.Draw(img)
big, small = font(112, 800), font(54, 500)

word = 'THE CREATION'
x = 0
for ch in word:  # tight tracking, like the old wordmark
    d.text((x, H * SS / 2), ch, font=big, fill=255, anchor='lm')
    x += d.textlength(ch, font=big) - 3 * SS
x += 38 * SS
d.rectangle([x, 12 * SS, x + 5 * SS, (H - 12) * SS], fill=255)
x += 5 * SS + 38 * SS
d.text((x, H * SS / 2), 'Foundation', font=small, fill=255, anchor='lm')
right = x + d.textlength('Foundation', font=small)
assert right <= W * SS, right / SS

alpha = img.resize((W, H), Image.LANCZOS)
out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
out.putalpha(alpha)
out.save('brand/creation-lockup.png', optimize=True)
print('lockup width used:', round(right / SS), 'of', W)
