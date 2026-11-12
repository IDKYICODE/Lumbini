"""Reusable kit for the villa: materials, walls/windows/doors, ceilings + bake lights, furniture, trees, sky.
Everything here is plan-independent; blender/villa.py holds the plan."""
import math, random
import bpy
import numpy as np
from mathutils import Vector
from lib import *          # noqa: F401,F403
import lib

CH = 2.95                  # false-ceiling height above the floor

# ---------------------------------------------------------------- materials
PAINT = mat('paint', '#EFEBE4', .9)
PAINT_W = mat('paintWarm', '#E8E0D3', .9)
CEIL = mat('ceiling', '#F6F4EF', .95)
EXT_W = mat('render', '#F2F0EB', .85)
EXT_D = mat('charcoal', '#3B3D3F', .8)
OCHRE = mat('ochre', '#C98E3A', .7)
MARBLE = mat('marble', '#FFFFFF', .12, tex='marble.jpg', tile=2.4, gloss=.55)
MARBLE_V = mat('marbleWall', '#FFFFFF', .15, tex='marble.jpg', tile=1.6, gloss=0.22)
OAKF = mat('oakFloor', '#FFFFFF', .35, tex='oak_planks.jpg', tile=2.4, gloss=0.1)
WALNUT = mat('walnut', '#FFFFFF', .4, tex='walnut_veneer', tile=1.2, gloss=0)
WALNUT_V = mat('walnutV', '#FFFFFF', .4, tex='walnut_veneer', tile=(1.2, 1.2), gloss=0)
TRIM = mat('walnutTrim', '#6A4630', .45, gloss=0)
TEAK = mat('teak', '#FFFFFF', .45, tex='teak_veneer', tile=1.5, gloss=0)
OAK = mat('oak', '#FFFFFF', .45, tex='oak_veneer_01', tile=1.2, gloss=0)
DECK = mat('deck', '#FFFFFF', .6, tex='wood_floor_deck', tile=2.0)
GRANITE = mat('granite', '#FFFFFF', .25, tex='granite_tile', tile=1.2, gloss=0.15)
PAVER = mat('paver', '#FFFFFF', .8, tex='concrete_pavers', tile=2.0)
STONE = mat('stoneClad', '#FFFFFF', .8, tex='stone_tile_wall', tile=2.0)
LAWN = mat('lawn', '#FFFFFF', 1., tex='lawn.jpg', tile=2.0)
QUARTZ = mat('quartz', '#F1EEE8', .2, gloss=0.18)
BRASS = mat('brass', '#B8925A', .3, metal=1., gloss=.2)
BRONZE = mat('bronze', '#6E5A44', .35, metal=1., gloss=.15)
BLACKM = mat('blackMetal', '#1E1F21', .4, metal=.8, gloss=.25)
ALU = mat('alu', '#2C2E31', .4, metal=.8, gloss=.2)
CHROME = mat('chrome', '#CFD2D6', .15, metal=1., gloss=.7)
GLASS = mat('glass', '#DDE8EE', 0., kind='glass', gloss=.9, double=True)
BRONZE_G = mat('bronzeGlass', '#6B5A48', .1, kind='glass', gloss=.8)
GREY_G = mat('greyGlass', '#5A5E62', .15, gloss=.6)
WATER = mat('water', '#6FB8C8', 0., kind='water', gloss=1., double=True)
BOUCLE = mat('boucle', '#E7DFD2', 1., tex='boucle.jpg', tile=.5)
BOUCLE2 = mat('boucleWhite', '#F3EFE8', 1., tex='boucle.jpg', tile=.5)
LINEN = mat('linen', '#D9CDB9', 1., tex='weave.jpg', tile=.4)
LINEN_W = mat('linenWhite', '#F4F1EB', 1., tex='weave.jpg', tile=.4)
TAUPE = mat('taupe', '#9C8C7A', 1., tex='weave.jpg', tile=.4)
NAVY = mat('navyVelvet', '#2A3A6A', .8, tex='velvet.jpg', tile=.6)
SAGE = mat('sageVelvet', '#6F8461', .8, tex='velvet.jpg', tile=.6)
TEAL = mat('tealVelvet', '#2F5C5A', .8, tex='velvet.jpg', tile=.6)
LEATHER = mat('leather', '#FFFFFF', .45, tex='brown_leather', tile=.8, gloss=0)
LEATHER_D = mat('leatherDark', '#4A4A4A', .45, tex='brown_leather', tile=.8, gloss=0)
CARPET_D = mat('carpetDark', '#FFFFFF', 1., tex='carpet_dark.jpg', tile=1.)
DRAPE = mat('drape', '#CDBFA9', 1., tex='weave.jpg', tile=.5)
DRAPE_D = mat('drapeDark', '#6E6458', 1., tex='weave.jpg', tile=.5)
FLUTED = mat('fluted', '#C9B9A2', .6, tex='fluted.jpg', tile=(.48, 3))
FLUTED_D = mat('flutedDark', '#3E3530', .6, tex='fluted.jpg', tile=(.48, 3))
LACQ = mat('lacquer', '#ECE7DF', .3, gloss=0.05)
LACQ_G = mat('lacquerGrey', '#7D7F82', .35, gloss=0.05)
WHITE = mat('white', '#F4F2EE', .5)
BLACK = mat('black', '#151618', .4, gloss=.3)
SOIL = mat('soil', '#3A2A1E', 1.)
PEBBLE = mat('pebble', '#D8D2C8', .8)
POT = mat('pot', '#D9D3C9', .6)
POT_D = mat('potDark', '#4B4642', .6)
PILLOW_A = mat('pillowA', '#CBB79A', 1., tex='weave.jpg', tile=.3)
PILLOW_B = mat('pillowB', '#2F4A5A', 1., tex='velvet.jpg', tile=.3)
PILLOW_C = mat('pillowC', '#B5734F', 1., tex='velvet.jpg', tile=.3)
JAALI = mat('jaali', '#FFFFFF', .7, tex='jaali.png', tile=.9, alpha=True, double=True)
LEAF_G = mat('leafGreen', '#FFFFFF', .7, tex='leaves_green.png', alpha=True, kind='alpha', double=True)
LEAF_P = mat('leafPink', '#FFFFFF', .7, tex='leaves_pink.png', alpha=True, kind='alpha', double=True)
BARK = mat('bark', '#4E3F33', .9)
LED = mat('led', '#FFFFFF', .5, emit='#FFD9A8', es=9, kind='emit')
LED_C = mat('ledCool', '#FFFFFF', .5, emit='#FFE8CC', es=6, kind='emit')
LAMP = mat('lampShade', '#F3E7D3', .8, emit='#FFD7A0', es=4, kind='emit')
DOWN = mat('downlight', '#FFFFFF', .5, emit='#FFE2BC', es=14, kind='emit')
SCREEN = mat('screen', '#FFFFFF', .2, tex='screen.jpg', emit='#FFFFFF', es=1.2, kind='emit')
STARS = mat('stars', '#FFFFFF', .9, tex='stars.jpg', tile=3., emit='#FFFFFF', es=.6, kind='emit')
MURAL = mat('mural', '#FFFFFF', .9, tex='mural.jpg')
ARTS = [mat(f'art{i}', '#FFFFFF', .8, tex=f'art{i}.jpg') for i in range(4)]
RUG_CLOUD = mat('rugCloud', '#FFFFFF', 1., tex='rug_cloud.jpg')
RUG_LIVING = mat('rugLiving', '#FFFFFF', 1., tex='rug_living.jpg')
RUG_LOUNGE = mat('rugLounge', '#FFFFFF', 1., tex='rug_lounge.jpg')
TV_BLACK = mat('tvBlack', '#0B0C0E', .08, gloss=.6)


def blk(lv, x0, y0, x1, y1): blockrect(lv, x0, y0, x1, y1)

# ---------------------------------------------------------------- walls with openings
def wall(axis, line, a, b, z0, z1, t, mat_in=PAINT, mat_out=None, openings=(), skirt=None):
    """Straight wall centred on `line`; axis 'x' runs along x (at y=line), 'y' runs along y (at x=line).
    openings: dicts a, b (along the wall), s (sill height above z0), h (head height above z0), kind: door | window | gap.
    mat_out: material of the outer half (external walls); the inner half takes mat_in."""
    def slab_(s0, s1, h0, h1):
        if s1 - s0 < 1e-4 or h1 - h0 < 1e-4: return
        if mat_out is None:
            if axis == 'x': box(s0, line - t / 2, h0, s1, line + t / 2, h1, mat_in)
            else: box(line - t / 2, s0, h0, line + t / 2, s1, h1, mat_in)
        else:   # two halves so inside and outside get their own finish
            if axis == 'x':
                box(s0, line - t / 2, h0, s1, line, h1, mat_out if mat_out_side < 0 else mat_in)
                box(s0, line, h0, s1, line + t / 2, h1, mat_in if mat_out_side < 0 else mat_out)
            else:
                box(line - t / 2, s0, h0, line, s1, h1, mat_out if mat_out_side < 0 else mat_in)
                box(line, s0, h0, line + t / 2, s1, h1, mat_in if mat_out_side < 0 else mat_out)
    mat_out_side = getattr(wall, 'side', -1)
    cur = a
    for op in sorted(openings, key=lambda o: o['a']):
        slab_(cur, op['a'], z0, z1)
        s, h = op.get('s', 0.), op.get('h', 2.4)
        slab_(op['a'], op['b'], z0, z0 + s)
        slab_(op['a'], op['b'], z0 + h, z1)
        cur = op['b']
        k = op.get('kind')
        if k == 'window': window(axis, line, op['a'], op['b'], z0 + s, z0 + h, t, op.get('mull', 1.2), op.get('slide', False))
        if k == 'door': door(axis, line, op['a'], op['b'], z0, z0 + h, t, op.get('mat', WALNUT), op.get('face', 1))
        if k == 'open': open_door(axis, line, op['a'], op['b'], z0, z0 + h, t, op.get('mat', WALNUT), op.get('face', 1), op.get('leaves', 1))
        if k == 'slide': slider(axis, line, op['a'], op['b'], z0, z0 + h, t)
        if 'lv' in op and k in ('gap', 'open', 'slide'):
            a2 = (op['a'] + op['b']) / 2 if k == 'slide' else op['a']
            if axis == 'x': walk(op['lv'], a2 + .05, line - t / 2 - .2, op['b'] - .05, line + t / 2 + .2)
            else: walk(op['lv'], line - t / 2 - .2, a2 + .05, line + t / 2 + .2, op['b'] - .05)
            # keep doorways clear of plants: 0.8 m either side of the opening
            r_ = (op['a'], line - t / 2 - .8, op['b'], line + t / 2 + .8) if axis == 'x' else (line - t / 2 - .8, op['a'], line + t / 2 + .8, op['b'])
            LAYOUT.setdefault('keep', []).append([op['lv'], *lib._rect_world(*r_)])
    slab_(cur, b, z0, z1)
    if skirt is None: skirt = getattr(wall, 'skirt', None)
    if skirt:
        for side in skirt: _skirt(axis, line + side * (t / 2 + .006), a, b, z0, [o for o in openings if o.get('s', 0) < .05])


def _skirt(axis, at, a, b, z0, gaps):
    cur = a
    for g in sorted(gaps, key=lambda o: o['a']) + [{'a': b, 'b': b}]:
        if g['a'] - cur > .02:
            if axis == 'x': box(cur, at - .007, z0 + .02, g['a'], at + .007, z0 + .11, TRIM)
            else: box(at - .007, cur, z0 + .02, at + .007, g['a'], z0 + .11, TRIM)
        cur = g['b']


def window(axis, line, a, b, z0, z1, t, mull=1.2, slide=False):
    f = .05; d = .07
    def fr(s0, s1, h0, h1):
        if axis == 'x': box(s0, line - d / 2, h0, s1, line + d / 2, h1, ALU)
        else: box(line - d / 2, s0, h0, line + d / 2, s1, h1, ALU)
    fr(a, b, z0, z0 + f); fr(a, b, z1 - f, z1); fr(a, a + f, z0, z1); fr(b - f, b, z0, z1)
    n = max(1, round((b - a) / mull))
    for i in range(1, n):
        s = a + (b - a) * i / n; fr(s - f / 2 - (.02 if slide else 0), s + f / 2, z0, z1)
    if axis == 'x': box(a, line - .006, z0, b, line + .006, z1, GLASS)
    else: box(line - .006, a, z0, line + .006, b, z1, GLASS)
    # sill / reveal lining
    if axis == 'x':
        box(a, line - t / 2 - .02, z0 - .03, b, line + t / 2 + .02, z0, QUARTZ)
    else:
        box(line - t / 2 - .02, a, z0 - .03, line + t / 2 + .02, b, z0, QUARTZ)


def _frame3(axis, line, a, b, z0, z1, t):
    f = .06
    def fr(s0, s1, h0, h1):
        if axis == 'x': box(s0, line - (t + .03) / 2, h0, s1, line + (t + .03) / 2, h1, TRIM, bevel=.003)
        else: box(line - (t + .03) / 2, s0, h0, line + (t + .03) / 2, s1, h1, TRIM, bevel=.003)
    fr(a - f, a, z0, z1 + f); fr(b, b + f, z0, z1 + f); fr(a - f, b + f, z1, z1 + f)


def open_door(axis, line, a, b, z0, z1, t, m=WALNUT, face=1, leaves=1):
    """Door standing open against the wall on the `face` side (hinged at a; a double door hinges at both jambs)."""
    _frame3(axis, line, a, b, z0, z1, t)
    w = (b - a) / leaves; n0 = line + face * t / 2
    for hinge, sgn in ([(a, 1), (b, -1)][:leaves]):
        h = hinge + sgn * .03
        if axis == 'x':
            box(h - .0225, n0, z0 + .005, h + .0225, n0 + face * w, z1 - .003, m, bevel=.003)
            box(h + .03 * sgn - .01, n0 + face * (w - .14), z0 + .9, h + .03 * sgn + .01, n0 + face * (w - .1), z0 + 1.35, BRASS)
        else:
            box(n0, h - .0225, z0 + .005, n0 + face * w, h + .0225, z1 - .003, m, bevel=.003)
            box(n0 + face * (w - .14), h + .03 * sgn - .01, z0 + .9, n0 + face * (w - .1), h + .03 * sgn + .01, z0 + 1.35, BRASS)


def slider(axis, line, a, b, z0, z1, t):
    """Sliding glass door, half open: fixed pane + slid pane both on the first half, the second half is open."""
    m = (a + b) / 2; f, d = .05, .07
    def fr(s0, s1, h0, h1, off=0.):
        if axis == 'x': box(s0, line - d / 2 + off, h0, s1, line + d / 2 + off, h1, ALU)
        else: box(line - d / 2 + off, s0, h0, line + d / 2 + off, s1, h1, ALU)
    def gl(s0, s1, off):
        if axis == 'x': box(s0, line + off - .006, z0 + f, s1, line + off + .006, z1 - f, GLASS)
        else: box(line + off - .006, s0, z0 + f, line + off + .006, s1, z1 - f, GLASS)
    fr(a, b, z1 - f, z1); fr(a, b, z0, z0 + .015); fr(a, a + f, z0, z1); fr(b - f, b, z0, z1)
    for off in (-.035, .035):
        fr(m - f, m, z0, z1, off); fr(a + f, a + f + .04, z0, z1, off); gl(a + f, m - f, off)


def door(axis, line, a, b, z0, z1, t, m=WALNUT, face=1, leaves=1):
    """Closed door: frame + leaf + handle (face: which side gets the handle, +1 / -1 along the wall normal)."""
    f = .06
    def fr(s0, s1, h0, h1, dd, mm):
        if axis == 'x': box(s0, line - dd / 2, h0, s1, line + dd / 2, h1, mm, bevel=.003)
        else: box(line - dd / 2, s0, h0, line + dd / 2, s1, h1, mm, bevel=.003)
    fr(a - f, a, z0, z1 + f, t + .03, TRIM); fr(b, b + f, z0, z1 + f, t + .03, TRIM); fr(a - f, b + f, z1, z1 + f, t + .03, TRIM)
    fr(a + .002, b - .002, z0 + .005, z1 - .003, .045, m)
    # brass pull handle on the visible face
    hx = b - .12
    for s in (face,):
        off = s * .045
        if axis == 'x':
            box(hx - .012, line + off - .01, z0 + .9, hx + .012, line + off + .01, z0 + 1.35, BRASS, bevel=.004)
        else:
            box(line + off - .01, hx - .012, z0 + .9, line + off + .01, hx + .012, z0 + 1.35, BRASS, bevel=.004)


def bm_rot_box(w, L, h, ang):
    """A box of length L along y, tilted by ang about x, centred on the current frame origin."""
    import bmesh as _bm
    from mathutils import Matrix as _M
    bm = _bm.new(); _bm.ops.create_cube(bm, size=1); _bm.ops.scale(bm, vec=(w, L, h), verts=bm.verts)
    _bm.ops.rotate(bm, cent=(0, 0, 0), matrix=_M.Rotation(ang, 3, 'X'), verts=bm.verts)
    lib._emit(bm, EXT_D)

def balcony_set(tea=False):
    """Two rope-and-teak lounge chairs facing each other across a round teak table."""
    for sy in (-.55, .55):
        with frame(0, sy, 0, 0 if sy < 0 else 180):
            for a in (-.27, .27):
                for b in (-.25, .25): box(a - .02, b - .02, 0, a + .02, b + .02, .4, TEAK, bevel=.005)
            box(-.3, -.28, .36, .3, .28, .4, TEAK, bevel=.008)
            box(-.29, -.27, .4, .29, .25, .48, LINEN_W, bevel=.04, seg=2)
            box(-.3, -.32, .4, .3, -.27, .82, TEAK, bevel=.008)
            box(-.27, -.27, .48, .27, -.18, .78, PILLOW_A, bevel=.05, seg=2)
    lathe(0, 0, 0, [(.18, 0), (.18, .02), (.04, .05), (.04, .44)], TEAK, 20); cyl(0, 0, .44, .48, .26, TEAK, 32)
    if tea: model('tea_set_01', 0, 0, .48, width=.26)


def swing(hang=2.85):
    """Teak porch swing (jhoola) on four brass chains."""
    box(-.7, -.3, .42, .7, .3, .48, TEAK, bevel=.01)
    box(-.7, .24, .48, .7, .3, .95, TEAK, bevel=.01)
    box(-.65, -.26, .48, .65, .2, .58, LINEN_W, bevel=.04)
    for sx in (-.6, .2):
        box(sx, .05, .58, sx + .42, .22, .9, PILLOW_A if sx < 0 else PILLOW_C, bevel=.05)
    for sx in (-.66, .66):
        for sy in (-.26, .26):
            tube([(sx, sy, .48), (sx, sy * .6, hang)], .008, BRASS, segs=6)


# ---------------------------------------------------------------- ceilings + lights
LIGHTS = []


def spot_light(x, y, z, power=60, size=.06, color=(1, .86, .72), angle=70):
    LIGHTS.append(('SPOT', (x, y, z), power, size, color, angle))


def downlight(x, y, z, power=55):
    cyl(x, y, z - .004, z + .004, .045, DOWN, 16); cyl(x, y, z + .001, z + .006, .058, BLACKM, 20)
    spot_light(x, y, z - .02, power)


def false_ceiling(x0, y0, x1, y1, z_floor, cove=.45, led=LED, downs=(), drop=.2):
    """Gypsum ceiling at CH with a perimeter cove: LED strip hidden on top of the dropped band washes the recess."""
    zc = z_floor + CH; zr = zc + drop
    box(x0, y0, zr, x1, y1, zr + .02, CEIL)          # recess (slab underside finish)
    for (a0, b0, a1, b1) in ((x0, y0, x1, y0 + cove), (x0, y1 - cove, x1, y1), (x0, y0 + cove, x0 + cove, y1 - cove), (x1 - cove, y0 + cove, x1, y1 - cove)):
        box(a0, b0, zc, a1, b1, zc + .1, CEIL)
    # strips
    i0, j0, i1, j1 = x0 + cove, y0 + cove, x1 - cove, y1 - cove
    for (a0, b0, a1, b1) in ((i0, j0 - .06, i1, j0 - .03), (i0, j1 + .03, i1, j1 + .06), (i0 - .06, j0, i0 - .03, j1), (i1 + .03, j0, i1 + .06, j1)):
        box(a0, b0, zc + .1, a1, b1, zc + .115, led)
    # rim to fill to the recess
    for (a0, b0, a1, b1) in ((x0, y0, x1, y0 + .02), (x0, y1 - .02, x1, y1), (x0, y0, x0 + .02, y1), (x1 - .02, y0, x1, y1)):
        box(a0, b0, zc + .1, a1, b1, zr, CEIL)
    for (x, y) in downs: downlight(x, y, zc)
    # area light in the recess so the bake sees the cove glow strongly
    LIGHTS.append(('AREA', ((x0 + x1) / 2, (y0 + y1) / 2, zc + .14), 60 * (x1 - x0) * (y1 - y0) / 10, (x1 - x0 - 2 * cove, y1 - y0 - 2 * cove), (1, .84, .66), 'UP'))


def flat_ceiling(x0, y0, x1, y1, z_floor, downs=()):
    zc = z_floor + CH
    box(x0, y0, zc, x1, y1, zc + .02, CEIL)
    for (x, y) in downs: downlight(x, y, zc)


def linear_pendant(x, y, z_floor, length=1.6, ry=0., drop=1.0):
    """Geometric brass pendant from the film: two thin rectangular loops, one tilted."""
    zc = z_floor + CH; zp = zc - drop
    with frame(x, y, 0, ry):
        for k, (w, d, tilt) in enumerate(((length, .5, 0), (length * .8, .4, .12))):
            zz = zp + k * .14
            pts = [(-w / 2, -d / 2, zz), (w / 2, -d / 2, zz + tilt), (w / 2, d / 2, zz + tilt), (-w / 2, d / 2, zz), (-w / 2, -d / 2, zz)]
            tube(pts, .012, BRASS, segs=6)
        box(-length / 2 + .05, -.012, zp - .02, length / 2 - .05, .012, zp - .005, LED)
        for sx in (-length / 3, length / 3): tube([(sx, 0, zp), (sx, 0, zc)], .003, BLACKM, segs=4)
    LIGHTS.append(('AREA', (x, y, zp - .03), 40, (length, .1), (1, .85, .7), 'DOWN'))


# ---------------------------------------------------------------- furniture library (local: front faces +y)
def sofa(w, d=.95, m=BOUCLE, base=WALNUT, back=.22, arms=.2, seat=.42):
    box(-w / 2, -d / 2, .06, w / 2, d / 2, .14, base, bevel=.01)
    box(-w / 2 + .03, -d / 2 + .03, 0, w / 2 - .03, d / 2 - .03, .06, BLACKM)
    box(-w / 2, -d / 2, .14, w / 2, -d / 2 + back, .8, m, bevel=.05, seg=2)
    for sx in (-1, 1):
        box(sx * (w / 2) - (arms if sx > 0 else 0), -d / 2, .14, sx * (w / 2) + (0 if sx > 0 else arms), d / 2, .62, m, bevel=.05, seg=2)
    n = max(1, round((w - 2 * arms) / .85)); cw = (w - 2 * arms) / n
    for i in range(n):
        cx = -w / 2 + arms + cw * (i + .5)
        box(cx - cw / 2 + .01, -d / 2 + back, .14, cx + cw / 2 - .01, d / 2 - .02, seat, m, bevel=.06, seg=2)
        box(cx - cw / 2 + .03, -d / 2 + back - .02, seat, cx + cw / 2 - .03, -d / 2 + back + .14, .78, m, bevel=.07, seg=2)


def cushion(x, y, z, m, s=.45, rot=0., tilt=.25):
    with frame(x, y, z, rot):
        box(-s / 2, -.07, 0, s / 2, .07, s, m, bevel=.06, seg=2)


def coffee_table(r=.55, top=MARBLE_V, base=BRONZE, h=.38):
    lathe(0, 0, 0, [(r * .55, 0), (r * .45, .02), (r * .3, h * .5), (r * .5, h - .03), (r * .5, h - .03)], base, 32)
    cyl(0, 0, h - .03, h, r, top, 48)


def rug(x0, y0, x1, y1, m, z):
    box(x0, y0, z, x1, y1, z + .012, m, uv='fit', bevel=.004)


OWN_POT = ('potted_plant_02', 'potted_plant_04')       # these scans come in their own pot


PLANT_REQ = []


def plant(name, x, y, z, h, pot=POT, pr=.22, ph=.42, variant=0, fixed=False):
    """A potted floor plant. Placement is resolved by place_plants() at the end of the build, once every piece of
    furniture exists: the real leaf spread is measured and the plant nudged until its canopy clears furniture and walls."""
    PLANT_REQ.append(dict(name=name, x=x, y=y, z=z, h=h, pot=pot, pr=pr, ph=ph, variant=variant, zone=lib._zone[-1], fixed=fixed))


def place_plants(levels_z):
    from mathutils import Matrix as _M
    lv_of = lambda zz: min(range(len(levels_z)), key=lambda i: abs(levels_z[i] - zz))
    def inside_walk(lv, px, py):
        return any((w[0] == lv or (w[0] is None and lv == 0)) and w[1] <= px <= w[3] and w[2] <= py <= w[4] for w in LAYOUT['walk'])
    for r in PLANT_REQ:
        lv = lv_of(r['z'])
        own = lambda b: b[0] == lv and b[1] - .05 <= r['x'] <= b[3] + .05 and b[2] - .05 <= r['y'] <= b[4] + .05 and b[3] - b[1] < 1. and b[4] - b[2] < 1.
        LAYOUT['block'][:] = [b for b in LAYOUT['block'] if not own(b)]          # hand-placed boxes for this plant go
        obstacles = [b[1:] for b in LAYOUT['block'] if b[0] == lv] + [b[1:] for b in LAYOUT.get('keep', []) if b[0] == lv]
        own_pot = r['name'] in OWN_POT
        base = r['z'] if own_pot else r['z'] + r['ph'] * .86
        with zone(r['zone']):
            objs = model(r['name'], r['x'], r['y'], base, height=r['h'], variant=r['variant'])
        v = [p.co for o in objs for p in o.data.vertices if p.co.z > base + .05] or [p.co for o in objs for p in o.data.vertices]
        xs = sorted(p.x for p in v); ys = sorted(p.y for p in v); k = max(0, len(xs) // 50)
        hx, hy = (xs[-1 - k] - xs[k]) / 2 + .07, (ys[-1 - k] - ys[k]) / 2 + .07         # canopy half-size + 7 cm air
        ox, oy = (xs[-1 - k] + xs[k]) / 2 - r['x'], (ys[-1 - k] + ys[k]) / 2 - r['y']   # canopy offset from the pot
        def fits(px, py):
            if r['fixed']: return True          # placed by hand in a spot nobody walks (e.g. under the stair)
            cx, cy = px + ox, py + oy
            for (b0, b1, b2, b3) in obstacles:
                if cx + hx > b0 and cx - hx < b2 and cy + hy > b1 and cy - hy < b3: return False
            def reach(tx, ty):      # every point from the pot to the canopy edge stays on this room's floor (no wall in between)
                n = max(2, int(math.hypot(tx - px, ty - py) / .04))
                return all(inside_walk(lv, px + (tx - px) * i / n, py + (ty - py) * i / n) for i in range(n + 1))
            return all(reach(cx + sx * hx, cy + sy * hy) for sx in (-1, 0, 1) for sy in (-1, 0, 1))
        best = None
        for rad in [0] + [i * .06 for i in range(1, 10)]:          # move at most ~0.55 m, otherwise leave the plant out
            for a in range(0, 360, 20 if rad else 360):
                px, py = r['x'] + rad * math.cos(math.radians(a)), r['y'] + rad * math.sin(math.radians(a))
                if fits(px, py): best = (px, py); break
            if best: break
        if not best:
            print('PLANT dropped (no clear spot)', r['name'], 'at', round(r['x'], 2), round(r['y'], 2))
            for o in objs:
                if o in lib.MODELS: lib.MODELS.remove(o)
                bpy.data.objects.remove(o)
            continue
        dx, dy = best[0] - r['x'], best[1] - r['y']
        if dx or dy:
            for o in objs: o.data.transform(_M.Translation((dx, dy, 0)))
            print(f'PLANT {r["name"]} moved {math.hypot(dx, dy):.2f} m to clear furniture/walls')
        px, py = best
        with zone(r['zone']):
            if not own_pot:
                pr, ph = r['pr'], r['ph']
                lathe(px, py, r['z'], [(pr * .75, 0), (pr, ph * .1), (pr, ph), (pr - .02, ph), (pr - .03, ph * .9)], r['pot'], 28)
                cyl(px, py, r['z'] + ph * .86, r['z'] + ph * .88, pr - .03, SOIL, 20)
        rr = .26 if own_pot else r['pr'] + .04
        LAYOUT['block'].append([lv, round(px - rr, 3), round(py - rr, 3), round(px + rr, 3), round(py + rr, 3)])


def armchair(m=BOUCLE2, w=.85, d=.85):
    lathe(0, 0, 0, [(.25, 0), (.25, .05), (.06, .07), (.06, .16)], BRONZE, 24)
    box(-w / 2, -d / 2, .16, w / 2, d / 2, .44, m, bevel=.08, seg=2)
    box(-w / 2, -d / 2, .44, w / 2, -d / 2 + .22, .82, m, bevel=.1, seg=2)
    for sx in (-1, 1): box(sx * w / 2 - (.18 if sx > 0 else 0), -d / 2, .44, sx * w / 2 + (0 if sx > 0 else .18), d / 2 - .05, .62, m, bevel=.08, seg=2)


def side_table(h=.55, top=MARBLE_V):
    cyl(0, 0, 0, .02, .16, BRONZE, 20); cyl(0, 0, .02, h - .03, .02, BRONZE, 10); cyl(0, 0, h - .03, h, .24, top, 32)


def dining_chair(m=NAVY):
    for sx in (-.2, .2):
        for sy in (-.2, .2): box(sx - .018, sy - .018, 0, sx + .018, sy + .018, .45, WALNUT)
    box(-.24, -.24, .43, .24, .24, .5, m, bevel=.03)
    with frame(0, -.24, .5, 0):
        box(-.24, -.03, 0, .24, .04, .42, m, bevel=.03)


def bed(w=1.95, L=2.15, quilt=LINEN_W, throw=TAUPE, head=None):
    with frame(0, L / 2, 0, 180): _bed(w, L, quilt, throw, head)


def _bed(w, L, quilt, throw, head):
    box(-w / 2 - .08, -L / 2, .08, w / 2 + .08, L / 2, .32, WALNUT, bevel=.02)          # base
    box(-w / 2, -L / 2 + .02, .32, w / 2, L / 2 - .05, .56, LINEN_W, bevel=.08, seg=2)   # mattress
    box(-w / 2 - .02, -L / 2 + .02, .5, w / 2 + .02, L / 2 - .45, .6, quilt, bevel=.06, seg=2)
    box(-w / 2 - .03, -L / 2 + .05, .58, w / 2 + .03, -L / 2 + .55, .63, throw, bevel=.04, seg=2)   # throw at the foot
    for sx in (-w / 4, w / 4):
        box(sx - .36, L / 2 - .5, .56, sx + .36, L / 2 - .12, .74, LINEN_W, bevel=.07, seg=2)
        box(sx - .3, L / 2 - .62, .58, sx + .3, L / 2 - .45, .9, PILLOW_A, bevel=.06, seg=2)
    if head: box(-w / 2 - .2, L / 2 - .02, .3, w / 2 + .2, L / 2 + .1, 1.35, head, bevel=.05, seg=2)


def nightstand(lamp=True):
    box(-.28, -.22, .18, .28, .22, .55, WALNUT, bevel=.008)
    box(-.27, .222, .3, .27, .225, .32, BRASS)
    for sx in (-.24, .24): box(sx - .015, -.2, 0, sx + .015, .2, .18, BRONZE)
    if lamp:
        lathe(0, -.02, .55, [(.07, 0), (.08, .05), (.03, .25), (.015, .32)], mat('ceramic', '#D8CFC2', .3, gloss=.2), 20)
        lathe(0, -.02, .82, [(.16, 0), (.13, .22)], LAMP, 28)
        LIGHTS.append(('POINT', None, 18, .08, (1, .78, .55), 0))


def wardrobe(w, h=2.7, d=.62, m=WALNUT_V, n=None):
    n = n or max(2, round(w / .55))
    box(-w / 2, -d, 0, w / 2, 0, .08, BLACKM)
    for i in range(n):
        x0 = -w / 2 + w * i / n
        box(x0 + .003, -d, .08, x0 + w / n - .003, -.02, h, m, bevel=.003)
        hx = x0 + (w / n - .05 if i % 2 == 0 else .05)
        box(hx - .008, -.03, 1.0, hx + .008, .012, 1.6, BRASS, bevel=.003)


def tv_unit(w, m=WALNUT):
    box(-w / 2, -.45, .18, w / 2, 0, .55, m, bevel=.006)
    box(-w / 2 + .02, -.455, .5, w / 2 - .02, -.448, .51, LED)
    box(-.95, -.08, 1.1, .95, -.03, 2.17, TV_BLACK, bevel=.006)
    box(-.93, -.081, 1.12, .93, -.079, 2.15, mat('tvGlass', '#16181B', .05, gloss=.8))


# ---------------------------------------------------------------- partition walls (internal)
def iwall(axis, line, a, b, z0, z1, openings=(), m=PAINT, m2=None):
    """Internal wall; openings as in wall(). m2: second face finish (the +side)."""
    wall.side = -1
    wall(axis, line, a, b, z0, z1, IT, m, m2, openings=openings)


# ---------------------------------------------------------------- garden, plot, neighbours
def card_tree(x, y, h, crown, leaf=LEAF_G, n=26, seed=0, avoid=()):
    """avoid: [(x0, y0, x1, y1)] footprints no leaf card may overlap (the house)."""
    r = random.Random(seed)
    tube([(x, y, 0), (x + .05, y, h * .4), (x - .05, y + .05, h * .62)], .09, BARK, segs=8)
    for k in range(3):
        a = k * 2.1; tube([(x, y, h * .45), (x + math.cos(a) * crown * .45, y + math.sin(a) * crown * .45, h * .7)], .045, BARK, segs=6)
    for i in range(n):
        cx = x + r.uniform(-1, 1) * crown * .55; cy = y + r.uniform(-1, 1) * crown * .55; cz = h * .62 + r.uniform(0, 1) * h * .38
        s = r.uniform(.9, 1.5); a = r.uniform(0, math.pi); tilt = r.uniform(-.6, .6)
        ux, uy = math.cos(a) * s, math.sin(a) * s
        if any(cx - s - .3 < ax1 and cx + s + .3 > ax0 and cy - s - .3 < ay1 and cy + s + .3 > ay0 for ax0, ay0, ax1, ay1 in avoid): continue
        quad([(cx - ux, cy - uy, cz - s * .8 + tilt), (cx + ux, cy + uy, cz - s * .8 - tilt), (cx + ux, cy + uy, cz + s * .8 - tilt), (cx - ux, cy - uy, cz + s * .8 + tilt)], leaf)
        quad([(cx - s, cy, cz + r.uniform(-.2, .2)), (cx + s, cy, cz), (cx + s, cy + .01, cz + 1e-3), (cx - s, cy + .01, cz + 1e-3)], leaf) if False else None
        quad([(cx - s * .9, cy - s * .9, cz), (cx + s * .9, cy - s * .9, cz + .1), (cx + s * .9, cy + s * .9, cz), (cx - s * .9, cy + s * .9, cz - .1)], leaf)


# ---------------------------------------------------------------- world + bake lights
def lighting(sc, SUN_AZ=30., SUN_EL=35., SUN_AZ_HDRI=0.):
    w = bpy.data.worlds.new('sky'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes['Background']
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(str(SRC / 'hdri' / 'kloofendal_48d_partly_cloudy_puresky.hdr'))
    mp = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(SUN_AZ_HDRI))
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    nt.links.new(env.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = .9
    # the sun: late-afternoon light from the south-west, so it rakes the front facade and the jaali
    bpy.ops.object.light_add(type='SUN', rotation=(math.radians(90 - SUN_EL), 0, math.radians(SUN_AZ)))
    s = bpy.context.object; s.data.energy = 4.2; s.data.color = (1., .9, .78); s.data.angle = math.radians(1.2); s.name = 'Sun'
    for L in LIGHTS:
        kind = L[0]
        if kind == 'SPOT':
            _, pos, power, size, col, ang = L
            bpy.ops.object.light_add(type='SPOT', location=pos); o = bpy.context.object
            o.data.energy = power; o.data.shadow_soft_size = size; o.data.color = col; o.data.spot_size = math.radians(ang); o.data.spot_blend = .6
        elif kind == 'AREA':
            _, pos, power, size, col, d = L
            rot = (0, 0, 0) if d == 'DOWN' else (math.pi, 0, 0)
            bpy.ops.object.light_add(type='AREA', location=pos, rotation=rot); o = bpy.context.object
            o.data.shape = 'RECTANGLE'; o.data.size, o.data.size_y = (size if isinstance(size, tuple) else (size, size)); o.data.energy = power; o.data.color = col
        elif kind == 'UP':
            _, pos, power, size, col, ang = L
            bpy.ops.object.light_add(type='SPOT', location=pos, rotation=(math.pi, 0, 0)); o = bpy.context.object
            o.data.energy = power; o.data.shadow_soft_size = size; o.data.color = col; o.data.spot_size = math.radians(ang); o.data.spot_blend = .5
        elif kind == 'POINT' and L[1]:
            _, pos, power, size, col, _a = L
            bpy.ops.object.light_add(type='POINT', location=pos); o = bpy.context.object
            o.data.energy = power; o.data.shadow_soft_size = size; o.data.color = col


SUN_AZ, SUN_EL, SUN_AZ_HDRI = -35., 38., 0.