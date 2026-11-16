'''Draws src/komgasync.png (32x32): two arrows chasing round a circle, the
usual "sync" symbol, in Komga's purple. Run once; needs Pillow.'''
from PIL import Image, ImageDraw

S = 4                      # draw at 4x, then downscale for smooth edges
size = 32 * S
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
purple = (103, 58, 183, 255)
d.ellipse((0, 0, size - 1, size - 1), fill=purple)

white = (255, 255, 255, 255)
box = (7 * S, 7 * S, 25 * S, 25 * S)
w = int(2.6 * S)
d.arc(box, 200, 340, fill=white, width=w)      # top arc
d.arc(box, 20, 160, fill=white, width=w)       # bottom arc
# arrow heads at the end of each arc
d.polygon([(25 * S, 12 * S), (28 * S, 17 * S), (22 * S, 17 * S)], fill=white)
d.polygon([(7 * S, 20 * S), (4 * S, 15 * S), (10 * S, 15 * S)], fill=white)

img.resize((32, 32), Image.LANCZOS).save('src/komgasync.png')
print('wrote src/komgasync.png')
