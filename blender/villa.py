"""Lumbini Vana — 350 sq yd East-facing villa (G+2, 4478 sq ft), built procedurally from the brochure plan.

Run:  blender -b -P blender/villa.py [-- --preview [Spot name ...]]
Writes build/villa.blend and build/layout.json (walk areas, stairs, collision, teleport spots, probes).

The plan is entered in PLAN PIXELS: coordinates read off refs/brochure/e350_{gf,ff,sf}.jpg (the brochure plan,
enlarged 4x). X(px), Y(py) convert to metres. To use a corrected plan, change the pixel numbers below.
Image orientation: bottom = East (road, front), right = North, top = West (rear), left = South.
World: x to the image right, y to the image top (so the road is at -y), z up.
"""
import sys, math, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import bpy
import numpy as np
from mathutils import Vector
from lib import *          # noqa: F401,F403
import lib
sc = reset()
from kit import *          # noqa: F401,F403  (materials need the fresh scene)
import kit

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

# ---------------------------------------------------------------- plan pixels -> metres
SX, SY = .3048 / 21.3, .3048 / 22.7            # metres per plan pixel (the brochure image is slightly anisotropic)
def X(px): return round((px - 20) * SX, 4)
def Y(py): return round((1330 - py) * SY, 4)
def P(px, py): return X(px), Y(py)
def R(px0, py0, px1, py1): return X(min(px0, px1)), Y(max(py0, py1)), X(max(px0, px1)), Y(min(py0, py1))

GF, FF, SF, ROOF = .45, 3.75, 7.05, 10.35
SLAB, WT, IT = .2, .23, .12
LV_G, LV_GF, LV_FF, LV_SF = level('Garden', 0.), level('Ground floor', GF), level('First floor', FF), level('Second floor', SF)
LVZ = [0., GF, FF, SF]

# plan lines (pixels)
L, RT, TOP, FR = 95, 862, 188, 1158            # building: left (south), right (north), top (rear/west), front (east)
SW0, SW1, SB0, SB1, SB2 = 105, 432, 545, 630, 722    # stair well x, bands y (upper band = arrival flight)
LAND = 210                                      # landing ends at this x


def walk_px(lv, *r): walk(lv, *R(*r))
def blk_px(lv, *r): blockrect(lv, *R(*r))


# ---------------------------------------------------------------- wall helpers in plan pixels
def Wh(py, px0, px1, z0, z1, t=IT, m=PAINT, m2=None, ops=(), side=-1, ext=False):
    """Image-horizontal wall (constant py) = world wall along x at Y(py). side: which world side (-y/+y) is 'outer' (m2)."""
    wall.side = side; wall.skirt = [-side] if ext else [-1, 1]
    wall('x', Y(py), X(px0), X(px1), z0, z1, t, m, m2, openings=[dict(d, a=X(d['a']), b=X(d['b'])) for d in ops])


def Wv(px, py0, py1, z0, z1, t=IT, m=PAINT, m2=None, ops=(), side=-1, ext=False):
    """Image-vertical wall (constant px) = world wall along y at X(px)."""
    wall.side = side; wall.skirt = [-side] if ext else [-1, 1]
    wall('y', X(px), Y(max(py0, py1)), Y(min(py0, py1)), z0, z1, t, m, m2,
         openings=[dict(d, a=Y(max(d['a'], d['b'])), b=Y(min(d['a'], d['b']))) for d in ops])


def ext_walls(z0, z1, segs):
    """segs: ('h'|'v', line, a, b, outer side, openings) — external walls, render outside, paint inside."""
    for kind, line, a, b, side, ops in segs:
        (Wh if kind == 'h' else Wv)(line, a, b, z0, z1, WT, PAINT, EXT_W, ops, side, ext=True)
    wall.skirt = None


def lift_door(z, wall_px=SW1):
    """Brushed steel lift doors on the lobby face of the shaft wall (py 725..862), with a call button and a floor sign."""
    x = X(wall_px) + IT / 2; y0, y1 = Y(845), Y(742)
    box(x, y0 - .2, z + 2.25, x + .025, y1 + .2, z + 2.45, mat('liftFrame', '#2A2B2D', .4, metal=.8))        # lintel band
    box(x, y0 - .06, z, x + .03, y1 + .06, z + 2.25, mat('liftFrame', '#2A2B2D', .4, metal=.8))
    box(x + .03, y0, z, x + .045, (y0 + y1) / 2 - .005, z + 2.15, CHROME); box(x + .03, (y0 + y1) / 2 + .005, z, x + .045, y1, z + 2.15, CHROME)
    box(x + .03, y1 + .1, z + 1.05, x + .04, y1 + .16, z + 1.2, BLACKM); sphere(x + .045, y1 + .13, z + 1.13, .012, LED)


# ---------------------------------------------------------------- stair (U, flights along x)
def stair(z0, lv_from, lv_to, top=False):
    xa, xb = X(LAND), X(SW1) - IT / 2                 # flights run between these x
    yl0, yl1, yu0, yu1 = Y(SB2), Y(SB1), Y(SB1), Y(SB0)    # lower band (start), upper band (arrival)
    n = 10; run = (xb - xa) / n; rh = (FF - GF) / 22; zl = z0 + rh * 11
    for k in range(1, n + 1):                         # flight 1: lower band, climbs toward -x
        x1 = xb - run * (k - 1); x0_ = x1 - run; zt = z0 + rh * k
        box(x0_ - .02, yl0 + .03, zt - .06, x1, yl1 - .03, zt, TEAK, bevel=.004)
        box(x1 - .03, yl0 + .08, zt - .075, x1 - .015, yl1 - .08, zt - .065, LED)          # step light under the nosing
    box(X(SW0), yl0, zl - .2, xa, yu1, zl - .02, CEIL); box(X(SW0), yl0, zl - .02, xa, yu1, zl, TEAK)     # landing
    for k in range(1, n + 1):                         # flight 2: upper band, climbs toward +x
        x0_ = xa + run * (k - 1); zt = zl + rh * k
        box(x0_, yu0 + .03, zt - .06, x0_ + run + .02, yu1 - .03, zt, TEAK, bevel=.004)
        box(x0_ + .015, yu0 + .08, zt - .075, x0_ + .03, yu1 - .08, zt - .065, LED)
    # charcoal stringers + glass balustrade with a brass rail along the middle
    for (ya, za, zb, xs, xe) in ((yl0 + .6, z0, zl, xb, xa), (yu0 + .55, zl, z0 + rh * 22, xa, xb)):
        Lg = math.hypot(xe - xs, zb - za); ang = math.atan2(zb - za, xe - xs)
        with frame((xs + xe) / 2, ya, (za + zb) / 2 - .22, 0):
            import bmesh as _bm
            from mathutils import Matrix as _M
            bm = _bm.new(); _bm.ops.create_cube(bm, size=1); _bm.ops.scale(bm, vec=(Lg, .24, .18), verts=bm.verts)
            _bm.ops.rotate(bm, cent=(0, 0, 0), matrix=_M.Rotation(-ang, 3, 'Y'), verts=bm.verts); lib._emit(bm, EXT_D)
    # stairwell finishes: fluted walnut on the long wall, book-matched marble on the landing wall, a wall-wash light
    wy = Y(SB2) + IT / 2
    box(X(SW0), wy, z0, X(SW1) - .05, wy + .025, z0 + (FF - GF) - SLAB, mat('flutedWalnut', '#FFFFFF', .45, tex='walnut_veneer', tile=(.06, 3.)))
    for xx in np.arange(X(SW0) + .3, X(SW1) - .1, .3): box(xx - .006, wy + .025, z0, xx + .006, wy + .032, z0 + (FF - GF) - SLAB, BRONZE)
    wx = X(L) + WT / 2
    box(wx, Y(SB2), z0, wx + .03, Y(SB0), z0 + (FF - GF) - SLAB, MARBLE_V)
    LIGHTS.append(('AREA', (X(SW0) + .6, (Y(SB2) + Y(SB0)) / 2, zl + 2.3), 70, (1.0, 2.0), (1, .85, .68), 'DOWN'))
    ym = Y(SB1)
    for (xs, xe, za, zb) in ((xb, xa, z0, zl), (xa, xb, zl, z0 + rh * 22)):
        for k in range(6):
            t0, t1 = k / 6, (k + 1) / 6; zz = za + (zb - za) * (t0 + t1) / 2
            box(min(xs + (xe - xs) * t0, xs + (xe - xs) * t1), ym - .006, zz, max(xs + (xe - xs) * t0, xs + (xe - xs) * t1), ym + .006, zz + .95, GLASS)
        tube([(xs, ym, za + 1.0), (xe, ym, zb + 1.0)], .02, BRASS, segs=8)
    ramp(xa, yl0, xb + .25, yl1, '-x', z0, zl, lv_from, None)
    ramp(X(SW0), yl0, xa, yu1, 'x', zl, zl, None, None)
    ramp(xa, yu0, xb + .25, yu1, 'x', zl, z0 + rh * 22, None, lv_to)


# ---------------------------------------------------------------- slabs + facade
def slab_rects(z, rects, holes=(), top=None):
    for r in rects:
        pieces = [r]
        for h in holes:
            nr = []
            for (a0, b0, a1, b1) in pieces:
                hx0, hy0, hx1, hy1 = h
                if hx1 <= a0 or hx0 >= a1 or hy1 <= b0 or hy0 >= b1: nr.append((a0, b0, a1, b1)); continue
                if hy0 > b0: nr.append((a0, b0, a1, hy0))
                if hy1 < b1: nr.append((a0, hy1, a1, b1))
                if hx0 > a0: nr.append((a0, max(b0, hy0), hx0, min(b1, hy1)))
                if hx1 < a1: nr.append((hx1, max(b0, hy0), a1, min(b1, hy1)))
            pieces = nr
        for (a0, b0, a1, b1) in pieces:
            box(a0, b0, z - SLAB, a1, b1, z - .02, CEIL)
            if top: box(a0, b0, z - .02, a1, b1, z, top)


WELL = (R(SW0 - 8, SB0, SW1, SB2)[0], R(SW0 - 8, SB0, SW1, SB2)[1], X(SW1) - IT / 2, R(SW0 - 8, SB0, SW1, SB2)[3])   # ends where the first tread starts (no gap)


def structure():
    with zone('gf'):
        box(*R(L, TOP, RT, 862)[:2], -.3, *R(L, TOP, RT, 862)[2:], GF - .02, mat('plinth', '#6F6B66', .9))
        box(*R(L, 862, 757, FR)[:2], -.3, *R(L, 862, 757, FR)[2:], GF - .02, mat('plinth', '#6F6B66', .9))
        box(*R(L, TOP, RT, 862)[:2], GF - .02, *R(L, TOP, RT, 862)[2:], GF, MARBLE)
        box(*R(L, 862, 757, FR)[:2], GF - .02, *R(L, 862, 757, FR)[2:], GF, MARBLE)
        stair(GF, LV_GF, LV_FF)
    with zone('ff'):
        slab_rects(FF, [R(L, TOP, 870, FR)], holes=[WELL])
        box(*R(282, TOP, 727, 543)[:2], FF - .02, *R(282, TOP, 727, 543)[2:], FF, OAKF)       # master
        box(*R(232, 865, 727, FR)[:2], FF - .02, *R(232, 865, 727, FR)[2:], FF, OAKF)         # bedroom 2
        box(*R(440, 543, RT, 865)[:2], FF - .02, *R(440, 543, RT, 865)[2:], FF, MARBLE)       # lounge
        for r in (R(L, TOP, 282, 543), R(L, 722, 440, 865), R(L, 865, 232, FR)):
            box(r[0], r[1], FF - .02, r[2], r[3], FF, MARBLE)
        for r in (R(727, TOP, 870, 543), R(727, 865, 870, FR)):                                # balconies
            box(r[0], r[1], FF - .02, r[2], r[3], FF, DECK)
        stair(FF, LV_FF, LV_SF)
    with zone('sf'):
        slab_rects(SF, [R(L, TOP, 875, FR)], holes=[WELL])
        box(*R(278, TOP, 607, 543)[:2], SF - .02, *R(278, TOP, 607, 543)[2:], SF, OAKF)        # bedroom 3
        box(*R(440, 543, 607, 865)[:2], SF - .02, *R(440, 543, 607, 865)[2:], SF, MARBLE)      # lobby
        box(*R(L, 865, 607, FR)[:2], SF - .02, *R(L, 865, 607, FR)[2:], SF, CARPET_D)          # theatre
        for r in (R(L, TOP, 278, 543), R(L, 722, 440, 865)):
            box(r[0], r[1], SF - .02, r[2], r[3], SF, MARBLE)
        box(*R(607, TOP, 875, FR)[:2], SF - .02, *R(607, TOP, 875, FR)[2:], SF, mat('terraceTile', '#FFFFFF', .7, tex='terrazzo_tiles', tile=1.6))
    with zone('ext'):
        slab_rects(ROOF, [R(L - 15, TOP - 15, 620, FR + 20)])
        box(*R(L - 15, TOP - 15, 620, FR + 20)[:2], ROOF, *R(L - 15, TOP - 15, 620, FR + 20)[2:], ROOF + .3, EXT_W)
        # teak soffit under the roof overhangs + the front canopy over the terrace (like the brochure render)
        x0, y0, x1, y1 = R(L - 15, TOP - 15, 620, FR + 20)
        for (a0, b0, a1, b1) in ((x0, y0, x1, Y(FR)), (x0, Y(TOP), x1, y1), (x0, y0, X(L), y1)):
            box(a0, b0, ROOF - SLAB - .03, a1, b1, ROOF - SLAB, TEAK)
        cx0, cy0, cx1, cy1 = R(607, 930, 885, FR + 20)
        box(cx0, cy0, ROOF - .05, cx1, cy1, ROOF + .3, EXT_W); box(cx0, cy0, ROOF - .08, cx1, cy1, ROOF - .05, TEAK)
        box(cx1 - .25, cy0, SF, cx1, cy0 + .25, ROOF - .05, EXT_W)                               # one slim white column
        for xx in np.arange(cx0 + .6, cx1 - .3, 1.0):
            downlight(xx, (cy0 + cy1) / 2, ROOF - .08 - CH + (ROOF - SF - CH) * 0 if False else ROOF - .08 - kit.CH + 0, 25) if False else None
        for xx in np.arange(cx0 + .6, cx1 - .3, 1.0):
            cyl(xx, (cy0 + cy1) / 2, ROOF - .086, ROOF - .08, .04, DOWN, 16)


def facade():
    g0, g1 = GF - .02, FF - SLAB
    with zone('gf'):
        ext_walls(g0, g1, [
            ('h', FR, L, 757, -1, [dict(a=250, b=450, s=1.05, h=2.3, kind='window', mull=1.0),
                                    dict(a=522, b=600, s=0, h=2.6, kind='open', mat=TEAK, face=1, lv=LV_GF),
                                    dict(a=625, b=740, s=.45, h=2.6, kind='window', mull=.8)]),
            ('h', TOP, L, RT, 1, [dict(a=290, b=440, s=.75, h=2.6, kind='window', mull=1.1),
                                  dict(a=575, b=800, s=0, h=2.75, kind='window', mull=1.1)]),
            ('v', L, TOP, FR, -1, [dict(a=380, b=440, s=1.6, h=2.3, kind='window', mull=.8), dict(a=760, b=830, s=1.2, h=2.3, kind='window', mull=.8),
                                   dict(a=1040, b=1090, s=1.6, h=2.3, kind='window', mull=.8)]),
            ('v', RT, TOP, 862, 1, [dict(a=230, b=470, s=.45, h=2.6, kind='window', mull=1.1),
                                    dict(a=600, b=830, s=0, h=2.6, kind='slide', lv=LV_GF)]),
            ('v', 757, 862, FR, 1, [dict(a=930, b=1080, s=.75, h=2.6, kind='window', mull=1.0)]),
            ('h', 862, 757, RT, -1, [])])
    f0, f1 = FF - .02, SF - SLAB
    with zone('ff'):
        ext_walls(f0, f1, [
            ('h', FR, L, 727, -1, [dict(a=300, b=560, s=.6, h=2.6, kind='window', mull=1.1)]),
            ('h', TOP, L, 727, 1, [dict(a=380, b=600, s=.6, h=2.6, kind='window', mull=1.1)]),
            ('v', L, TOP, FR, -1, [dict(a=430, b=490, s=1.6, h=2.3, kind='window', mull=.8), dict(a=1050, b=1110, s=1.6, h=2.3, kind='window', mull=.8)]),
            ('v', 727, TOP, 543, 1, [dict(a=420, b=520, s=0, h=2.6, kind='slide', lv=LV_FF), dict(a=230, b=380, s=.6, h=2.6, kind='window', mull=1.0)]),
            ('v', 727, 865, FR, 1, [dict(a=1000, b=1100, s=0, h=2.6, kind='slide', lv=LV_FF), dict(a=880, b=980, s=.6, h=2.6, kind='window', mull=1.0)]),
            ('v', RT, 543, 865, 1, [dict(a=590, b=820, s=.45, h=2.6, kind='window', mull=1.1)]),
            ('h', 543, 727, RT, 1, []), ('h', 865, 727, RT, -1, [])])
    s0, s1 = SF - .02, ROOF - SLAB
    with zone('sf'):
        ext_walls(s0, s1, [
            ('h', FR, L, 607, -1, [dict(a=180, b=290, s=.9, h=2.4, kind='window', mull=1.0), dict(a=400, b=510, s=.9, h=2.4, kind='window', mull=1.0)]),
            ('h', TOP, L, 607, 1, [dict(a=340, b=540, s=.75, h=2.6, kind='window', mull=1.1)]),
            ('v', L, TOP, FR, -1, [dict(a=430, b=490, s=1.6, h=2.3, kind='window', mull=.8)]),
            ('v', 607, TOP, FR, 1, [dict(a=250, b=470, s=0, h=2.6, kind='slide', lv=LV_SF), dict(a=560, b=760, s=0, h=2.6, kind='slide', lv=LV_SF)])])
    with zone('ext'):
        # slab bands (charcoal) around the floor edges
        for z, (x0, y0, x1, y1) in ((FF, R(L, TOP, 870, FR)), (SF, R(L, TOP, 875, FR))):
            for (a0, b0, a1, b1) in ((x0 - .05, y0 - .05, x1 + .05, y0), (x0 - .05, y1, x1 + .05, y1 + .05), (x0 - .05, y0, x0, y1), (x1, y0, x1 + .05, y1)):
                box(a0, b0, z - .28, a1, b1, z + .02, EXT_D)
        # plinth in stone
        for r in (R(L, TOP, RT, 862), R(L, 862, 757, FR)):
            box(r[0] - .04, r[1] - .04, -.05, r[2] + .04, r[3] + .04, GF - .03, mat('plinthStone', '#FFFFFF', .8, tex='stone_tile_wall', tile=1.2))
        # FRONT: the jaali box (charcoal frame, grey screen) wrapping bedroom 2 + its balcony on the first floor
        jx0, jy0, jx1, _ = R(232, FR, 875, FR)
        fy = Y(FR) - .45
        box(jx0, fy, FF - .3, jx0 + .25, Y(FR) + .02, SF + .1, EXT_D); box(jx1 - .25, fy, FF - .3, jx1, Y(865), SF + .1, EXT_D)
        box(jx0, fy, SF - .15, jx1, Y(FR) + .02, SF + .1, EXT_D); box(jx0, fy, FF - .3, jx1, Y(FR) + .02, FF - .02, EXT_D)
        box(jx0 + .25, fy + .02, FF, jx1 - .25, fy + .06, SF - .15, JAALI)
        box(jx0 + .25, fy + .06, FF - .02, jx1 - .25, Y(FR), FF, DECK)
        # balcony glass rails (north side)
        for (py0, py1) in ((TOP, 543), (865, FR)):
            xx = X(870) - .05; a, b = Y(py1), Y(py0)
            box(xx - .006, a, FF, xx + .006, b, FF + 1.05, GLASS); tube([(xx, a, FF + 1.06), (xx, b, FF + 1.06)], .02, BLACKM)
        ny = Y(TOP) - .05                                                    # master balcony's open north end
        box(X(727), ny - .006, FF, X(870) - .05, ny + .006, FF + 1.05, GLASS)
        tube([(X(727), ny, FF + 1.06), (X(870) - .05, ny, FF + 1.06)], .02, BLACKM)
        box(X(870) - .07, ny - .02, FF, X(870) - .03, ny + .02, FF + 1.06, BLACKM)
        # terrace parapet + glass rail
        tx0, ty0, tx1, ty1 = R(607, TOP, 875, FR)
        for (a0, b0, a1, b1) in ((tx1 - .2, ty0, tx1, ty1), (X(607), ty1 - .2, tx1, ty1), (X(607), ty0, tx1, ty0 + .2)):
            box(a0, b0, SF - .02, a1, b1, SF + .3, EXT_W)
        for (a0, b0, a1, b1) in ((tx1 - .11, ty0 + .2, tx1 - .09, ty1 - .2), (X(607), ty1 - .11, tx1 - .2, ty1 - .09), (X(607), ty0 + .09, tx1 - .2, ty0 + .11)):
            box(a0, b0, SF + .3, a1, b1, SF + 1.1, GLASS)
        tube([(X(607), ty0 + .1, SF + 1.12), (tx1 - .1, ty0 + .1, SF + 1.12), (tx1 - .1, ty1 - .1, SF + 1.12), (X(607), ty1 - .1, SF + 1.12)], .02, BLACKM)
        # ground-floor front: grey vertical fluting beside the door, stone cladding at the door, teak door surround
        fx = Y(FR) - WT / 2 - .02
        for xx in np.arange(X(L) + .05, X(245), .1):
            box(xx, fx - .04, GF, xx + .05, fx, FF - .3, EXT_D)
        box(X(600) + .08, fx - .03, GF, X(622), fx, FF - .3, mat('stoneFront', '#FFFFFF', .8, tex='stone_tile_wall', tile=1.0))
        box(X(510), fx - .05, GF, X(520), fx, GF + 2.7, TEAK); box(X(510), fx - .05, GF + 2.6, X(612), fx, GF + 2.7, TEAK)
        # entrance steps (3 risers) + landing in granite, a planter either side
        sx0, sy0, sx1, sy1 = R(490, 1165, 665, 1290)
        box(sx0, sy1 - .3, -.05, sx1, Y(FR), GF, GRANITE, bevel=.005)
        box(sx0, sy1 - .6, -.05, sx1, sy1 - .3, .3, GRANITE, bevel=.005); box(sx0, sy1 - .9, -.05, sx1, sy1 - .6, .15, GRANITE, bevel=.005)
        ramp(sx0 + .1, sy1 - .95, sx1 - .1, sy1 - .3, 'y', 0., GF, LV_G, LV_GF)
        walk(LV_GF, sx0 + .1, sy1 - .3, sx1 - .1, Y(FR) + .1)
        # carport: flat roof with a teak soffit on slim black columns, at the north-east corner
        cx0, cy0, cx1, cy1 = R(757, 875, 1140, 1240)
        box(X(870), cy0, FF - .3, cx1, cy1, FF - .02, EXT_W); box(X(870), cy0, FF - .33, cx1, cy1, FF - .3, TEAK)
        for (xx, yy) in ((cx1 - .15, cy0 + .15), (cx1 - .15, cy1 - .15)):
            box(xx - .05, yy - .05, 0, xx + .05, yy + .05, FF - .33, BLACKM)
            blockrect(LV_G, xx - .1, yy - .1, xx + .1, yy + .1)
        for xx in np.arange(X(890), cx1 - .3, .9):
            cyl(xx, (cy0 + cy1) / 2, FF - .336, FF - .33, .04, DOWN, 16)


def kitchen_tower(x0, x1, yf, z):
    """Floor-to-ceiling kitchen tower, front face at y=yf facing -y: French-door fridge, oven stack (oven, microwave,
    warming drawer), pantry. Doors with 3 mm shadow gaps and slim black pulls; nothing straddles a door."""
    TAUPE_L = mat('lacquerTaupe', '#B8AEA2', .3, gloss=.04)
    n = 5; w = (x1 - x0) / n; d = .6
    box(x0, yf + .06, z, x1, yf + d, z + .1, BLACKM)                                        # recessed plinth
    def panel(a, b, h0, h1, m=TAUPE_L):
        box(a + .0015, yf, z + h0 + .0015, b - .0015, yf + d, z + h1 - .0015, m, bevel=.002)
    def vpull(x, h0, h1): box(x - .006, yf - .025, z + h0, x + .006, yf, z + h1, BLACKM, bevel=.002)
    def hpull(a, b, h): box(a, yf - .025, z + h - .006, b, yf, z + h + .006, BLACKM, bevel=.002)
    c = [x0 + w * i for i in range(n + 1)]
    # fridge: two tall doors meeting in the middle, pulls at the meeting edge
    panel(c[0], c[1], .1, 2.0); panel(c[1], c[2], .1, 2.0); vpull(c[1] - .05, .85, 1.55); vpull(c[1] + .05, .85, 1.55)
    panel(c[0], c[2], 2.0, 2.6); hpull(c[1] - .2, c[1] + .2, 2.06)
    # oven stack
    panel(c[2], c[3], .1, .75); hpull(c[2] + .12, c[3] - .12, .68)
    box(c[2] + .0015, yf, z + .78, c[3] - .0015, yf + d, z + 1.4, TV_BLACK, bevel=.002)              # oven, black glass
    box(c[2] + .03, yf - .002, z + 1.32, c[3] - .03, yf, z + 1.38, mat('ovenStrip', '#2A2C2F', .3))     # control strip
    tube([(c[2] + .08, yf - .04, z + 1.27), (c[3] - .08, yf - .04, z + 1.27)], .009, CHROME, segs=8)
    for xx in (c[2] + .08, c[3] - .08): box(xx - .006, yf - .04, z + 1.265, xx + .006, yf, z + 1.275, CHROME)
    box(c[2] + .0015, yf, z + 1.43, c[3] - .0015, yf + d, z + 1.82, TV_BLACK, bevel=.002)             # microwave
    box(c[3] - .09, yf - .002, z + 1.47, c[3] - .03, yf, z + 1.78, mat('ovenStrip', '#2A2C2F', .3))
    panel(c[2], c[3], 1.85, 2.6); hpull(c[2] + .12, c[3] - .12, 1.92)
    # pantry: two tall doors + top cupboards
    panel(c[3], c[4], .1, 2.0); panel(c[4], c[5], .1, 2.0); vpull(c[4] - .05, .85, 1.55); vpull(c[4] + .05, .85, 1.55)
    panel(c[3], c[5], 2.0, 2.6); hpull(c[4] - .2, c[4] + .2, 2.06)
    box(x0, yf, z + 2.6, x1, yf + d, z + CH, PAINT)                                                  # bulkhead to the ceiling


# ---------------------------------------------------------------- GROUND FLOOR
def ground_floor():
    z = GF; H = FF - SLAB; zc = z + CH
    with zone('gf'):
        # partitions
        Wh(540, L, 507, z, H, ops=[dict(a=440, b=500, h=2.4, kind='open', face=1, lv=LV_GF)])            # guest suite | below
        Wv(223, TOP, 540, z, H, ops=[dict(a=280, b=328, h=2.4, kind='gap')])                             # WIC/toilet | guest
        Wh(332, L, 223, z, H, ops=[dict(a=140, b=200, h=2.2, kind='door', face=-1)])                     # WIC | toilet
        Wv(507, TOP, 540, z, H, m=PAINT, m2=PAINT)                                                       # guest | living (TV wall)
        # under flight 2 / the landing: an open pebble garden lit from below (no rooms squeezed under the stair)
        ux0, uy0, ux1, uy1 = X(SW0) + .02, Y(SB1) + .02, X(SW1) - .3, Y(SB0) - .02
        box(ux0, uy0, z, ux1, uy1, z + .06, PEBBLE)
        box(ux0, uy0, z, ux1, uy0 + .04, z + .1, WALNUT); box(ux1 - .04, uy0, z, ux1, uy1, z + .1, WALNUT)
        plant('calathea_orbifolia_01', (ux0 + ux1) / 2 + .3, (uy0 + uy1) / 2, z + .06, .75, pot=POT_D, pr=.2, ph=.35, fixed=True)
        model('brass_vase_03', ux1 - .45, uy0 + .3, z + .06, height=.45)
        LIGHTS.append(('UP', (ux1 - .7, (uy0 + uy1) / 2, z + .1), 25, .05, (1, .8, .55), 50))
        box(ux1 - .72, (uy0 + uy1) / 2 - .03, z + .06, ux1 - .66, (uy0 + uy1) / 2 + .03, z + .08, DOWN)
        Wh(722, L, SW1, z, H)                                                                            # stair band | maid/lift
        Wv(298, 722, 865, z, H, m=PAINT)                                                                 # maid | lift shaft
        Wv(SW1, 722, 865, z, H, m=LACQ_G)                                                                # lift front
        Wv(207 - 100, 722, 865, z, H) if False else None
        Wh(865, L, SW1, z, H, ops=[dict(a=150, b=210, h=2.2, kind='door', face=1)])                      # maid | kitchen
        Wv(507, 865, FR, z, H, ops=[dict(a=870, b=960, h=2.4, kind='gap')])                              # kitchen | drawing
        Wh(862, 600, 757, z, H)                                                                          # drawing | dining (crockery)
        Wv(222, 915, 1100, z, H, ops=[dict(a=960, b=1010, h=2.2, kind='door', face=1), dict(a=1040, b=1090, h=2.2, kind='door', face=1)])
        Wh(1027, L, 222, z, H)
        lift_door(z)
        # ---- drawing room (entrance): L sofa, coffee table, armchair, art, chandelier
        x0, y0, x1, y1 = R(510, 865, 757, FR)
        false_ceiling(x0 + .06, y0 + WT / 2, x1 - WT / 2, y1 - .06, z, downs=[(x0 + .5, y0 + .5), (x1 - .5, y0 + .5), (x0 + .5, y1 - .5), (x1 - .5, y1 - .5)])
        with frame(x1 - WT / 2 - .5, (y0 + y1) / 2 + .3, z, 90): sofa(2.4)
        with frame((x0 + x1) / 2 + .35, y1 - .5, z, 180): sofa(1.7)
        cushion(x1 - .62, (y0 + y1) / 2 - .2, z + .44, PILLOW_B, rot=90); cushion(x1 - .62, (y0 + y1) / 2 + .9, z + .44, PILLOW_C, rot=90)
        with frame(X(638), Y(985), z, 0): coffee_table(r=.48)
        model('tea_set_01', X(630), Y(985), z + .38, width=.38)
        with frame(X(638), Y(1068), z, 0): armchair(m=SAGE); seat('Drawing room', LV_GF, 0, .05, .44)
        rug(X(560), Y(1080), X(735), Y(905), RUG_LIVING, z)
        picture('y', y1 - .065 if False else Y(865) - IT / 2 - .004, X(520), X(600), z + 1.2, z + 2.3, ARTS[2], facing=-1) if False else None
        model('Chandelier_02', X(638), Y(985), zc - .85, height=.75)
        LIGHTS.append(('POINT', (X(638), Y(985), zc - .6), 50, .2, (1, .8, .6), 0))
        blk_px(LV_GF, 690, 875, 757, 1060); blk_px(LV_GF, 575, 875, 757, 935); blk_px(LV_GF, 595, 955, 685, 1015)
        blk_px(LV_GF, 605, 1036, 671, 1100)
        walk(LV_GF, x0, y0, x1, y1)
        probe('drawing', LV_GF, x0, y0, z, x1, y1, z + CH)
        # ---- dining (open to living): table for six, linear brass pendant, backlit crockery unit
        x0, y0, x1, y1 = R(SW1, 545, RT, 862)
        flat_ceiling(X(SW1) + IT / 2, y0, X(RT) - WT / 2, y1, z, downs=[(X(470), Y(600)), (X(470), Y(800)), (X(830), Y(800))])
        tx, ty = P(735, 680)
        with frame(tx, ty, z, 90):
            box(-.5, -1.15, .72, .5, 1.15, .76, WALNUT, bevel=.008)
            box(-.06, -.75, 0, .06, .75, .72, BRONZE); box(-.3, -.8, 0, .3, -.7, .04, BRONZE); box(-.3, .7, 0, .3, .8, .04, BRONZE)
            for sy in (-.72, 0, .72):
                with frame(-.62, sy, 0, -90): dining_chair()
                with frame(.62, sy, 0, 90): dining_chair()
            seat('Dining', LV_GF, -.62, 0, .5, face=(1, 0))
            model('ceramic_vase_01', 0, .25, .76, height=.3)
            for sy in (-.6, .6): box(-.18, sy - .14, .76, .18, sy + .14, .765, LINEN)
        blk(LV_GF, tx - 1.3, ty - .85, tx + 1.3, ty + .85)
        linear_pendant(tx, ty, z, length=1.7, ry=0)
        cx0, cy0, cx1, cy1 = R(605, 815, 858, 862)
        box(cx0, cy0, z, cx1, cy1, z + 2.4, WALNUT, bevel=.004)
        box(cx0 + .05, cy1 - .02, z + .9, cx1 - .05, cy1, z + 2.3, BRONZE_G)
        for k in range(3): box(cx0 + .05, cy0 + .05, z + 1.25 + k * .38, cx1 - .05, cy1 - .03, z + 1.27 + k * .38, GREY_G)
        box(cx0 + .05, cy0 + .05, z + 2.3, cx1 - .05, cy1 - .03, z + 2.32, LED)
        box(cx0 + .05, cy1, z + .85, cx1 - .05, cy1 + .02, z + .87, LED)
        blockrect(LV_GF, cx0, cy0, cx1, cy1 + .05)
        blk_px(LV_GF, SW1, 545, 470, 590)
        # ---- living: TV wall on the guest-room partition, L sofa, coffee table, two armchairs
        x0, y0, x1, y1 = R(507, TOP, RT, 545)
        false_ceiling(X(507) + IT / 2, y0, X(RT) - WT / 2, Y(TOP) - WT / 2, z, downs=[(X(560), Y(230)), (X(820), Y(230)), (X(560), Y(500)), (X(820), Y(500))])
        tvx = X(507) + IT / 2
        box(tvx, Y(540), z, tvx + .05, Y(195), zc, WALNUT_V)
        for (a, b) in ((Y(520), Y(450)), (Y(270), Y(200))):
            box(tvx + .05, a, z + .6, tvx + .32, b, zc - .2, BRONZE_G)
            for k in range(4): box(tvx + .05, a, z + .9 + k * .5, tvx + .32, b, z + .92 + k * .5, WALNUT)
            box(tvx + .05, a, zc - .22, tvx + .32, b, zc - .2, LED)
        with frame(tvx + .05, Y(360), z, 90): tv_unit(2.4)
        blk(LV_GF, tvx, Y(540), tvx + .55, Y(195))
        with frame(X(825), Y(330), z, 90): sofa(2.4); seat('Living', LV_GF, 0, .1, .48)
        with frame(X(745), Y(225), z, 180): sofa(1.9)
        cushion(X(842) - .1, Y(300), z + .44, PILLOW_B, rot=90); cushion(X(842) - .1, Y(380), z + .44, PILLOW_A, rot=90); cushion(X(745), Y(214) - .1, z + .44, PILLOW_C, rot=180)
        blk_px(LV_GF, 785, 195, RT, 420); blk_px(LV_GF, 670, 195, RT, 262)
        with frame(X(730), Y(310), z, 0): coffee_table()
        model('wooden_bowl_01', X(722), Y(305), z + .38, width=.3)
        blk_px(LV_GF, 690, 278, 775, 345)
        for xx in (720, 785):
            with frame(X(xx), Y(515), z, 0): armchair(m=BOUCLE2)
        blk_px(LV_GF, 685, 485, 815, 545)
        rug(X(600), Y(470), X(810), Y(230), RUG_CLOUD, z)
        plant('pachira_aquatica_01', X(612), Y(252), z, 1.6, pot=POT_D, pr=.25, ph=.45)
        blk_px(LV_GF, 615, 195, 665, 250); blk_px(LV_GF, 810, 425, 860, 470)
        for (a, b) in ((X(570), X(590)), (X(785), X(805))):
            box(a, Y(TOP) - WT / 2 - .1, z + .02, b + .1, Y(TOP) - WT / 2 - .02, z + 2.9, DRAPE, bevel=.02)
        model('modern_ceiling_lamp_01', X(730), Y(310), zc - .55, height=.5)
        walk(LV_GF, X(507) + IT / 2, Y(862), X(RT) - WT / 2, Y(TOP) - WT / 2)
        walk(LV_GF, X(SW1), Y(862), X(507), Y(545))
        probe('living', LV_GF, X(507) + .06, Y(862), z, X(RT) - .12, Y(TOP) - .12, z + CH)
        # ---- guest bedroom (rear-south corner)
        x0, y0, x1, y1 = R(223, TOP, 507, 540)
        false_ceiling(x0 + .06, y0 + .06, x1 - .06, y1 - WT / 2, z, downs=[(x0 + .5, y0 + .5), (x1 - .5, y0 + .5), (x0 + .5, y1 - .6), (x1 - .5, y1 - .6)])
        hx = X(365)
        box(hx - 1.5, y1 - WT / 2 - .05, z, hx + 1.5, y1 - WT / 2, z + 2.6, FLUTED)
        picture('y', y1 - WT / 2 - .055, hx - .6, hx + .6, z + 1.55, z + 2.3, ARTS[0], facing=-1)
        with frame(hx, y1 - WT / 2 - .05, z, 180):
            bed(head=mat('headLeather', '#8A6E55', .5, tex='brown_leather', tile=.8))
            with frame(-1.35, .32, 0, 0): nightstand()
            with frame(1.35, .32, 0, 0): nightstand()
        rug(hx - 1.3, y1 - 2.9, hx + 1.3, y1 - .9, RUG_CLOUD, z)
        blk(LV_GF, hx - 1.15, y1 - 2.4, hx + 1.15, y1); blk(LV_GF, hx - 1.7, y1 - .6, hx + 1.7, y1)
        with frame(X(330), y0 + IT / 2 + .62, z, 0): wardrobe(2.6, h=2.7)          # wardrobe on the bottom wall
        blk_px(LV_GF, 230, 495, 430, 540)
        with frame(X(478), Y(330), z, 90): armchair(m=SAGE); seat('Guest bedroom', LV_GF, 0, .05, .44)
        model('potted_plant_04', X(365) + 1.45, Y(TOP) - WT / 2 - .05 - .32, z + .55, height=.2)
        walk(LV_GF, x0, y0, x1, y1); walk_px(LV_GF, 105, 195, 223, 330)
        probe('guest', LV_GF, x0, y0, z, x1, y1, z + CH)
        flat_ceiling(X(L) + WT / 2, Y(332), X(223), Y(TOP) - WT / 2, z, downs=[(X(160), Y(260))])
        with frame(X(L) + WT / 2 + .62, Y(260), z, -90): wardrobe(1.6, h=2.6, m=LACQ)
        # ---- kitchen: tall units on the maid/lift wall, counter run on the front wall, peninsula, store + utility
        x0, y0, x1, y1 = R(222, 865, 507, FR)
        flat_ceiling(X(L) + WT / 2, y0, x1 - IT / 2, Y(865) - IT / 2, z, downs=[(X(300), Y(950)), (X(440), Y(950)), (X(300), Y(1080)), (X(440), Y(1080))])
        ky = Y(865) - IT / 2
        kitchen_tower(X(225), X(430), ky - .62, z)
        fy0 = Y(FR) + WT / 2
        box(X(225), fy0, z, X(505) - .05, fy0 + .62, z + .1, BLACKM)
        for xx in np.arange(X(225), X(505) - .1, .6):
            box(xx + .003, fy0, z + .1, min(xx + .6, X(505)) - .003, fy0 + .6, z + .87, WALNUT, bevel=.003)
        box(X(225), fy0 + .58, z + .78, X(505) - .05, fy0 + .6, z + .82, BLACKM)             # handle-less J-groove
        box(X(225), fy0, z + .87, X(505) - .05, fy0 + .64, z + .91, QUARTZ, bevel=.003)
        box(X(225), fy0, z + .91, X(505) - .05, fy0 + .02, z + 1.05, mat('backsplash', '#FFFFFF', .2, tex='marble.jpg', tile=1.0, gloss=.18))
        box(X(380), fy0 + .1, z + .91, X(430), fy0 + .5, z + .915, TV_BLACK)                       # hob
        box(X(270), fy0 + .12, z + .9, X(330), fy0 + .5, z + .91, CHROME)                           # sink
        tube([(X(300), fy0 + .06, z + .91), (X(300), fy0 + .06, z + 1.25), (X(300), fy0 + .3, z + 1.25)], .012, CHROME, segs=8)
        box(X(460), Y(1105), z, X(503), Y(975), z + .88, WALNUT, bevel=.003)                        # peninsula
        box(X(455), Y(1105), z + .88, X(507), Y(975), z + .92, QUARTZ, bevel=.003)
        model('tea_set_01', X(480), Y(1030), z + .92, width=.3)
        model('potted_plant_04', X(482), Y(1080), z + .92, height=.24)
        model('wooden_bowl_01', X(250), fy0 + .35, z + .91, width=.28)
        blk(LV_GF, X(100), ky - .65, X(SW1), ky); blk(LV_GF, X(225), fy0, X(507), fy0 + .66); blk_px(LV_GF, 452, 975, 507, 1105)
        walk(LV_GF, x0 + IT / 2, fy0 + .6, x1 - IT / 2, ky - .6); walk_px(LV_GF, SW1, 862, 507, 870)
        walk_px(LV_GF, 432, 860, 507, 975)
        for xx in (X(300), X(420)):
            lathe(xx, Y(1000), zc - .95, [(.0, 0), (.12, .02), (.09, .2), (.02, .24)], BRASS, 24)
            tube([(xx, Y(1000), zc - .71), (xx, Y(1000), zc)], .003, BLACKM, segs=4)
            LIGHTS.append(('POINT', (xx, Y(1000), zc - 1.0), 15, .05, (1, .82, .62), 0))
        probe('kitchen', LV_GF, x0, y0, z, x1, y1, z + CH)
        # ---- stair start + under-stair planter on the dining side
        walk_px(LV_GF, SW1, SB1, 470, SB2)
        flat_ceiling(X(SW1), Y(722), X(507), Y(545), z) if False else None


# ---------------------------------------------------------------- FIRST FLOOR
def first_floor():
    z = FF; H = SF - SLAB; zc = z + CH
    with zone('ff'):
        Wh(543, L, 727, z, H, ops=[dict(a=535, b=600, h=2.4, kind='open', face=-1, lv=LV_FF)])           # master | lounge/stair
        Wv(282, TOP, 543, z, H, ops=[dict(a=330, b=390, h=2.4, kind='gap', lv=LV_FF)])                    # WIC/toilet | master
        Wh(397, L, 282, z, H, ops=[dict(a=150, b=210, h=2.2, kind='door', face=1)])                      # WIC | toilet
        Wh(SB2, L, SW1 + 8, z, H)                                                                        # stair | WIC2/lift
        Wv(300, SB2, 865, z, H)                                                                          # WIC2 | lift
        Wv(SW1 + 8, SB2, 865, z, H, m=LACQ_G)                                                            # lift front
        Wh(865, L, 727, z, H, ops=[dict(a=540, b=600, h=2.4, kind='open', face=1, lv=LV_FF), dict(a=640, b=705, h=2.4, kind='gap')])   # lounge | bed 2 / pooja
        Wv(232, 865, FR, z, H, ops=[dict(a=880, b=940, h=2.4, kind='gap'), ])                             # bed 2 | WIC passage/toilet
        Wh(947, L, 232, z, H, ops=[dict(a=150, b=210, h=2.2, kind='door', face=-1)])
        Wv(607, 865, 997, z, H, m=PAINT_W)                                                               # pooja | bed 2
        Wh(997, 607, 727, z, H, m=PAINT_W)
        lift_door(z, SW1 + 8)
        # ---- family lounge: L sofa, mural on the west partition (stair side), arc lamp, TV unit
        x0, y0, x1, y1 = R(440, 543, RT, 865)
        false_ceiling(x0, y0 + IT / 2, x1 - WT / 2, y1 - IT / 2, z, downs=[(X(480), Y(580)), (X(830), Y(580)), (X(480), Y(830)), (X(830), Y(830))])
        with frame(X(830), Y(650), z, 90): sofa(2.4, m=mat('sofaCamel', '#B88B5A', .9, tex='velvet.jpg', tile=.6)); seat('Family lounge', LV_FF, 0, .1, .48)
        with frame(X(745), Y(578), z, 180): sofa(1.9, m=mat('sofaCamel', '#B88B5A', .9, tex='velvet.jpg', tile=.6))
        cushion(X(845) - .12, Y(620), z + .44, BOUCLE2, rot=90); cushion(X(845) - .12, Y(700), z + .44, PILLOW_B, rot=90)
        blk_px(LV_FF, 790, 548, RT, 740); blk_px(LV_FF, 665, 548, RT, 612)
        with frame(X(732), Y(665), z, 0): coffee_table(r=.48)
        model('ceramic_vase_03', X(725), Y(660), z + .38, height=.25)
        blk_px(LV_FF, 690, 635, 775, 695)
        with frame(X(622), Y(660), z, -90): armchair(m=BOUCLE2)
        blk_px(LV_FF, 585, 615, 660, 705)
        rug(X(600), Y(760), X(800), Y(600), RUG_LOUNGE, z)
        mx = X(612)
        picture('y', Y(865) + IT / 2 + .004, X(610), X(725), z + .1, z + 2.85, MURAL, facing=1) if False else None
        # mural: the long lounge wall that the sofa faces is the stair side (x = 440); paint it as a silk mural panel
        picture('x', X(440) + .004, Y(722), Y(548), z + .5, z + 2.7, MURAL, facing=1) if False else None
        box(X(725), Y(862), z, X(RT) - WT / 2, Y(815), z + .55, WALNUT, bevel=.006)
        with frame((X(725) + X(RT)) / 2, Y(815) + .05, z, 0):
            pass
        with frame(X(800), Y(830), z, 0):
            box(-.85, .0, 1.05, .85, .05, 2.0, TV_BLACK, bevel=.006)
        # arc floor lamp
        with frame(X(800), Y(770), z, 0):
            cyl(0, 0, 0, .04, .2, MARBLE_V, 28)
            tube([(0, 0, .04), (0, 0, 1.4), (-.3, .2, 2.0), (-.65, .55, 2.08), (-.85, .8, 1.9)], .014, BRASS, segs=8)
            lathe(-.85, .8, 1.62, [(.25, 0), (.24, .02), (.15, .2), (.03, .28)], BRASS, 32)
            cyl(-.85, .8, 1.62, 1.625, .23, LAMP, 32)
        LIGHTS.append(('POINT', (X(800) - .85, Y(770) + .8, z + 1.55), 30, .15, (1, .8, .58), 0))
        blk_px(LV_FF, 785, 760, 815, 790)
        blk_px(LV_FF, 600, 550, 650, 600); blk_px(LV_FF, 445, 815, 495, 862)
        walk(LV_FF, X(440), Y(865) + IT / 2, X(RT) - WT / 2, Y(543) - IT / 2)
        walk_px(LV_FF, SW1 - 5, SB0 + 3, 445, SB1)
        walk_px(LV_FF, SW1 - 5, SB1, 445, SB2 - 3)
        probe('lounge', LV_FF, x0, y0, z, x1, y1, z + CH)
        # mural on the lift/WIC wall facing the lounge? -> use the solid wall west of the pooja (lounge's south wall run)
        picture('y', Y(865) + IT / 2 + .004, X(440), X(535), z + .3, z + 2.8, MURAL, facing=1)
        # ---- master bedroom: headboard on the rear wall, sofa by the balcony, vanity, wardrobe/TV wall
        x0, y0, x1, y1 = R(282, TOP, 727, 543)
        false_ceiling(x0 + IT / 2, y0 + IT / 2, x1 - WT / 2, y1 - WT / 2, z, downs=[(x0 + .6, y0 + .6), (x1 - .6, y0 + .6), (x0 + .6, y1 - .6), (x1 - .6, y1 - .6)])
        hx = X(455); hy = Y(TOP) - WT / 2
        box(hx - 2.0, hy - .06, z, hx + 2.0, hy, z + 2.7, FLUTED)
        for dx in (-2.0, -1.0, 1.0, 2.0): box(hx + dx - .006, hy - .07, z, hx + dx + .006, hy - .06, z + 2.7, BRASS)
        picture('y', hy - .075, hx - .6, hx + .6, z + 1.55, z + 2.45, ARTS[1], facing=-1)
        box(hx - .65, hy - .07, z + 1.5, hx + .65, hy - .066, z + 2.5, BLACKM)
        with frame(hx, hy - .06, z, 180):
            bed(head=mat('headLeather', '#8A6E55', .5, tex='brown_leather', tile=.8))
            with frame(-1.4, .32, 0, 0): nightstand()
            with frame(1.4, .32, 0, 0): nightstand()
        for dx in (-1.55, 1.55):
            tube([(hx + dx, hy - .1, z + 1.25), (hx + dx, hy - .25, z + 1.55), (hx + dx, hy - .1, z + 1.9)], .012, BRASS, segs=6)
            sphere(hx + dx, hy - .25, z + 1.55, .05, LAMP)
        rug(hx - 1.5, hy - 3.0, hx + 1.5, hy - .9, RUG_CLOUD, z)
        blk(LV_FF, hx - 1.2, hy - 2.4, hx + 1.2, hy); blk(LV_FF, hx - 1.8, hy - .6, hx + 1.8, hy)
        with frame(X(690), Y(265), z, 90): sofa(1.7, m=SAGE); seat('Master bedroom', LV_FF, 0, .1, .48)
        with frame(X(620), Y(285), z, 0): side_table(h=.45)
        blk_px(LV_FF, 645, 200, 722, 335); blk_px(LV_FF, 600, 265, 640, 305)
        with frame(X(408), Y(543) + IT / 2 + .62, z, 0): wardrobe(2.8, h=2.7)
        blk_px(LV_FF, 290, 490, 528, 540)
        with frame(X(678), Y(500), z, 180):              # vanity with a round mirror
            box(-.5, -.45, .72, .5, 0, .76, WALNUT, bevel=.004); box(-.48, -.45, .3, .48, -.43, .72, WALNUT)
            cyl(0, -.02, 1.0, 1.0001, .01, BRASS) if False else None
        blk_px(LV_FF, 640, 465, 718, 540)
        model('potted_plant_04', X(700), Y(500) + .22, z + .76, height=.2)
        for (a, b) in ((Y(415), Y(400)), (Y(530), Y(515))):
            box(X(727) - WT / 2 - .1, a, z + .02, X(727) - WT / 2 - .02, b, z + 2.9, DRAPE, bevel=.02)
        walk(LV_FF, x0 + IT / 2, y0 + WT / 2, x1 - WT / 2, y1 - IT / 2)
        walk_px(LV_FF, 105, 195, 282, 395)
        with frame(X(L) + WT / 2 + .62, Y(290), z, -90): wardrobe(1.8, h=2.7)
        flat_ceiling(X(L) + WT / 2, Y(397), X(282), Y(TOP) - WT / 2, z, downs=[(X(190), Y(290))])
        probe('master', LV_FF, x0, y0, z, x1, y1, z + CH)
        # master balcony (north)
        bx0, by0, bx1, by1 = R(727, TOP, 870, 543)
        walk(LV_FF, bx0 + .1, by0 + .05, bx1 - .1, by1 - .05)
        with frame(X(800), Y(300), z, 0): balcony_set(tea=True); seat('Master balcony', LV_FF, 0, .55, .48, face=(1, 0))
        blk_px(LV_FF, 760, 250, 845, 355)
        plant('shrub_sorrel_01', X(800), Y(500), z, .75, pot=POT_D, pr=.24)
        blk_px(LV_FF, 770, 470, 835, 530)
        # ---- bedroom 2 (front): bed on the lounge wall, chairs by the window, wardrobe
        x0, y0, x1, y1 = R(232, 865, 607, FR)
        false_ceiling(x0 + IT / 2, y0 + WT / 2, X(727) - WT / 2, y1 - IT / 2, z, downs=[(X(300), Y(1100)), (X(680), Y(1100)), (X(300), Y(920))])
        hx = X(410); hy = Y(865) - IT / 2
        box(hx - 1.6, hy - .05, z, hx + 1.6, hy, z + 1.25, WALNUT_V); box(hx - 1.6, hy - .052, z + 1.25, hx + 1.6, hy, z + 1.27, BRASS)
        picture('y', hy - .055, hx - .55, hx + .55, z + 1.5, z + 2.3, ARTS[0], facing=-1)
        with frame(hx, hy - .05, z, 180):
            bed(w=1.8, L=2.1, quilt=mat('quiltGrey', '#D8D4CE', 1., tex='weave.jpg', tile=.4), throw=SAGE)
            with frame(-1.25, .32, 0, 0): nightstand(lamp=False)
            with frame(1.25, .32, 0, 0): nightstand(lamp=False)
        for dx in (-1.25, 1.25):
            lathe(hx + dx, hy - .3, z + 1.35, [(.0, 0), (.07, .02), (.05, .28), (.01, .3)], BLACK, 20)
            tube([(hx + dx, hy - .3, z + 1.65), (hx + dx, hy - .3, zc)], .003, BLACKM, segs=4)
            sphere(hx + dx, hy - .3, z + 1.36, .035, LAMP)
            LIGHTS.append(('POINT', (hx + dx, hy - .3, z + 1.3), 8, .04, (1, .8, .6), 0))
        rug(hx - 1.3, hy - 2.8, hx + 1.3, hy - .9, RUG_CLOUD, z)
        blk(LV_FF, hx - 1.1, hy - 2.3, hx + 1.1, hy); blk(LV_FF, hx - 1.6, hy - .6, hx + 1.6, hy)
        with frame(X(420), Y(FR) + WT / 2 + .62, z, 0): wardrobe(4.6, h=2.7)
        blk_px(LV_FF, 240, 1115, 600, FR)
        for xx in (628, 683):
            with frame(X(xx), Y(1125), z, 0): armchair(m=SAGE, w=.72, d=.75)
        with frame(X(628), Y(1125), z, 0): seat('Bedroom 2', LV_FF, 0, .05, .44)
        blk_px(LV_FF, 600, 1095, 720, FR)
        walk(LV_FF, x0 + IT / 2, Y(FR) + WT / 2, X(727) - WT / 2, Y(997) - IT / 2)
        walk(LV_FF, x0 + IT / 2, Y(FR) + WT / 2, X(607), Y(865) - IT / 2)
        walk_px(LV_FF, 105, 870, 232, 945)
        with frame(X(L) + WT / 2 + .62, Y(905), z, -90): wardrobe(1.0, h=2.6, m=LACQ)
        probe('bed2', LV_FF, x0, y0, z, X(727), y1, z + CH)
        bx0, by0, bx1, by1 = R(727, 865, 870, FR)
        walk(LV_FF, bx0 + .1, by0 + .1, bx1 - .1, by1 - .1)
        with frame(X(800), Y(960), z, 0): balcony_set(); seat('Bedroom 2 balcony', LV_FF, 0, .55, .48, face=(0, -1))
        blk_px(LV_FF, 760, 940, 845, 1045)
        with frame(X(815), Y(1105), z, 90): swing(hang=CH)
        blk_px(LV_FF, 735, 1090, 790, 1150)
        # ---- pooja room: marble back wall, arched brass niche, diyas, bells
        px0, py0, px1, py1 = R(607, 865, 727, 997)
        flat_ceiling(px0 + IT / 2, py0 + IT / 2, px1 - WT / 2, py1 - IT / 2, z, downs=[((px0 + px1) / 2, (py0 + py1) / 2)])
        bx = py0 + IT / 2                                         # the back wall (front-facing side) is y = Y(997)
        box(px0 + .06, bx, z, px1 - WT / 2, bx + .02, zc, MARBLE_V)
        box(px0 + .15, bx + .02, z, px1 - WT / 2 - .1, bx + .3, z + .75, WALNUT, bevel=.006)
        box(px0 + .13, bx + .02, z + .75, px1 - WT / 2 - .08, bx + .32, z + .8, MARBLE_V)
        cxp = (px0 + px1 - WT / 2 + .06) / 2
        for k in range(14):
            a0, a1 = math.pi * k / 14, math.pi * (k + 1) / 14
            tube([(cxp + .5 * math.cos(a), bx + .03, z + 1.5 + .5 * math.sin(a)) for a in (a0, a1)], .012, BRASS, segs=6)
        for sx in (-.5, .5): tube([(cxp + sx, bx + .03, z + .8), (cxp + sx, bx + .03, z + 1.5)], .012, BRASS, segs=6)
        box(cxp - .45, bx + .02, z + .82, cxp + .45, bx + .03, z + 1.45, mat('pujaGlow', '#FFFFFF', .5, emit='#FFC27A', es=2.2, kind='emit'))
        model('brass_diya_lantern', cxp - .3, bx + .18, z + .8, height=.3)
        model('brass_diya_lantern', cxp + .3, bx + .18, z + .8, height=.3)
        model('brass_pot_01', cxp, bx + .16, z + .8, height=.2)
        for k in range(3):
            bxx = px0 + .3 + k * .3
            tube([(bxx, py1 - .4, zc), (bxx, py1 - .4, zc - .45 - (k % 2) * .12)], .003, BRASS, segs=4)
            lathe(bxx, py1 - .4, zc - .6 - (k % 2) * .12, [(.045, 0), (.04, .04), (.025, .1), (.005, .12)], BRASS, 16)
        LIGHTS.append(('POINT', (cxp, bx + .5, z + 1.3), 20, .1, (1, .7, .4), 0))
        blockrect(LV_FF, px0, py0, px1, py1)


# ---------------------------------------------------------------- SECOND FLOOR
def second_floor():
    z = SF; H = ROOF - SLAB; zc = z + CH
    with zone('sf'):
        Wh(543, L, 607, z, H, ops=[dict(a=540, b=600, h=2.4, kind='open', face=-1, lv=LV_SF)])
        Wv(278, TOP, 543, z, H, ops=[dict(a=320, b=385, h=2.4, kind='gap', lv=LV_SF)])
        Wh(392, L, 278, z, H, ops=[dict(a=150, b=210, h=2.2, kind='door', face=1)])
        Wh(SB2, L, SW1 + 8, z, H)
        Wv(203, SB2, 865, z, H); Wv(300, SB2, 865, z, H)
        Wv(SW1 + 8, SB2, 865, z, H, m=LACQ_G, ops=[])
        Wh(865, L, 607, z, H, m=PAINT_W, m2=FLUTED_D, ops=[dict(a=540, b=600, h=2.3, kind='open', face=-1, lv=LV_SF)])
        Wh(722, 140, 190, z, H) if False else None
        lift_door(z, SW1 + 8)
        # glass guard where the stair well is open below
        gx = X(SW1); box(gx - .006, Y(SB2), z, gx + .006, Y(SB1), z + 1.05, GLASS); tube([(gx, Y(SB2), z + 1.06), (gx, Y(SB1), z + 1.06)], .02, BRASS)
        box(X(LAND), Y(SB1) - .006, z, X(SW1), Y(SB1) + .006, z + 1.05, GLASS); tube([(X(LAND), Y(SB1), z + 1.06), (X(SW1), Y(SB1), z + 1.06)], .02, BRASS)
        # ---- lobby
        x0, y0, x1, y1 = R(440, 543, 607, 865)
        flat_ceiling(x0, y0 + IT / 2, x1 - WT / 2, y1 - IT / 2, z, downs=[((x0 + x1) / 2, Y(600)), ((x0 + x1) / 2, Y(800))])
        flat_ceiling(X(SW0), Y(SB2), X(SW1), Y(SB0), ROOF - SLAB - CH - .02)                         # over the stair
        picture('x', X(607) - WT / 2 - .004, Y(858), Y(775), z + 1.2, z + 2.3, ARTS[2], facing=-1)        # art facing the lift
        box(X(607) - WT / 2 - .04, Y(861), z + 1.15, X(607) - WT / 2, Y(772), z + 2.35, BLACKM)
        walk(LV_SF, x0, y0 + IT / 2, x1 - WT / 2, y1 - IT / 2)
        walk_px(LV_SF, SW1 - 5, SB0 + 3, 445, SB1)
        probe('lobby', LV_SF, x0, y0, z, x1, y1, z + CH)
        # ---- bedroom 3
        x0, y0, x1, y1 = R(278, TOP, 607, 543)
        false_ceiling(x0 + IT / 2, y0 + IT / 2, x1 - WT / 2, y1 - WT / 2, z, downs=[(x0 + .5, y0 + .5), (x1 - .5, y0 + .5), (x0 + .5, y1 - .6), (x1 - .5, y1 - .6)])
        hx, hy = X(418), Y(TOP) - WT / 2
        box(hx - 1.4, hy - .05, z, hx + 1.4, hy, z + 2.7, FLUTED)
        picture('y', hy - .055, hx - .5, hx + .5, z + 1.55, z + 2.3, ARTS[3], facing=-1)
        with frame(hx, hy - .05, z, 180):
            bed(w=1.8, L=2.1, throw=TEAL)
            with frame(-1.25, .32, 0, 0): nightstand()
            with frame(1.25, .32, 0, 0): nightstand()
        rug(hx - 1.2, hy - 2.8, hx + 1.2, hy - .9, RUG_LIVING, z)
        blk(LV_SF, hx - 1.1, hy - 2.3, hx + 1.1, hy); blk(LV_SF, hx - 1.55, hy - .6, hx + 1.55, hy)
        with frame(X(400), Y(543) + IT / 2 + .62, z, 0): wardrobe(2.6, h=2.7)
        blk_px(LV_SF, 282, 500, 525, 543)
        model('potted_plant_04', X(418) + 1.25, Y(TOP) - WT / 2 - .35, z + .55, height=.22)
        blk_px(LV_SF, 545, 200, 600, 260)
        walk(LV_SF, x0 + IT / 2, y0 + WT / 2, x1 - WT / 2, y1 - IT / 2)
        walk_px(LV_SF, 105, 195, 278, 388)
        with frame(X(L) + WT / 2 + .62, Y(290), z, -90): wardrobe(1.6, h=2.6, m=LACQ)
        flat_ceiling(X(L) + WT / 2, Y(392), X(278), Y(TOP) - WT / 2, z, downs=[(X(190), Y(290))])
        probe('bed3', LV_SF, x0, y0, z, x1, y1, z + CH)
        # ---- home theatre: screen on the south wall, three tiers of two recliners, star ceiling
        x0, y0, x1, y1 = R(L, 865, 607, FR)
        ix0, iy0, ix1, iy1 = x0 + WT / 2, y0 + WT / 2, x1 - WT / 2, y1 - IT / 2
        box(ix0, iy0, z, ix1, iy0 + .04, zc, FLUTED_D)
        box(ix0, iy1 - .04, z, X(540) - .07, iy1, zc, FLUTED_D); box(X(600) + .07, iy1 - .04, z, ix1, iy1, zc, FLUTED_D)   # broken at the door
        box(ix1 - .04, iy0, z, ix1, iy1, zc, FLUTED_D)
        box(ix0, iy0, z, ix0 + .04, iy1, zc, mat('acoustic', '#24201D', 1., tex='weave.jpg', tile=.5))
        box(ix0, iy0, zc, ix1, iy1, zc + .02, STARS)
        for (a0, b0, a1, b1) in ((ix0, iy0, ix1, iy0 + .35), (ix0, iy1 - .35, ix1, iy1), (ix0, iy0, ix0 + .35, iy1), (ix1 - .35, iy0, ix1, iy1)):
            box(a0, b0, zc - .25, a1, b1, zc, mat('theatreSoffit', '#1C1A18', .9))
        for (a0, b0, a1, b1) in ((ix0 + .35, iy0 + .33, ix1 - .35, iy0 + .35), (ix0 + .35, iy1 - .35, ix1 - .35, iy1 - .33), (ix0 + .33, iy0 + .35, ix0 + .35, iy1 - .35), (ix1 - .35, iy0 + .35, ix1 - .33, iy1 - .35)):
            box(a0, b0, zc - .25, a1, b1, zc - .23, LED)
        box(ix0 + .04, iy0 + .35, z + .5, ix0 + .06, iy1 - .35, z + 2.45, mat('screenFrame', '#0A0A0A', .9))
        box(ix0 + .05, iy0 + .43, z + .58, ix0 + .06, iy1 - .43, z + 2.37, BLACKM)                     # screen frame
        picture('x', ix0 + .062, iy0 + .45, iy1 - .45, z + .6, z + 2.35, SCREEN, facing=1)             # one image, edge to edge
        for yy in (iy0 + .25, iy1 - .25):
            box(ix0 + .1, yy - .2, z, ix0 + .45, yy + .2, z + 1.1, BLACK, bevel=.01)
        SEAT = mat('reclinerLeather', '#9A7B66', .45, tex='brown_leather', tile=.8, gloss=0)
        tiers = [(X(228), 0.), (X(318), .2), (X(410), .4)]
        seats_y = (iy0 + .62, iy0 + 1.55)                       # two recliners per row, aisle along the door side
        for (xx, dz) in tiers:
            if dz:
                box(xx - .6, iy0, z, xx + .6, iy0 + 2.05, z + dz, CARPET_D)
                box(xx - .62, iy0, z + dz - .03, xx - .6, iy0 + 2.05, z + dz - .01, LED)
            for yy in seats_y:
                with frame(xx, yy, z + dz, -90):                # front of the recliner faces the screen (-x)
                    box(-.42, -.45, .05, .42, .45, .44, SEAT, bevel=.04)
                    box(-.42, .3, .44, .42, .48, 1.05, SEAT, bevel=.08, seg=2)
                    box(-.36, -.38, .44, .36, .3, .56, SEAT, bevel=.06, seg=2)
                    for sx in (-.42, .42): box(sx - .07, -.4, .44, sx + .07, .45, .68, SEAT, bevel=.04)
                    box(-.25, -.47, .1, .25, -.45, .12, LED)          # glow strip under the footrest
                    if dz == .2 and yy == seats_y[0]: seat('Home theatre', LV_SF, 0, -.05, .56, face=(0, -1))
        for yy in np.arange(iy0 + .3, iy1 - .2, .8):
            box(ix1 - .06, yy - .06, z + .3, ix1 - .04, yy + .06, z + .34, LED)     # step lights on the back wall
        for xx in (X(300), X(500)):
            LIGHTS.append(('POINT', (xx, iy1 - .5, zc - .35), 22, .3, (1, .8, .6), 0))
        LIGHTS.append(('POINT', ((ix0 + ix1) / 2, iy0 + 1.1, zc - .35), 18, .3, (1, .8, .6), 0))
        probe('theatre', LV_SF, ix0, iy0, z, ix1, iy1, z + CH)
    with zone('sf'):    # ---- terrace (open, north side): pergola lounge, plunge pool, loungers, planters
        tx0, ty0, tx1, ty1 = R(607, TOP, 875, FR)
        walk(LV_SF, tx0 + .1, ty0 + .25, tx1 - .25, ty1 - .25)
        # pergola over the rear half with teak battens
        pg = (ty1 - 4.5, ty1 - .3)                     # starts north of the lobby's sliding door
        for xx in (tx0 + .35, tx1 - .45):
            for yy in pg: box(xx - .06, yy - .06, z, xx + .06, yy + .06, z + 2.8, BLACKM); blockrect(LV_SF, xx - .1, yy - .1, xx + .1, yy + .1)
            box(xx - .06, pg[0], z + 2.8, xx + .06, pg[1], z + 2.95, BLACKM)
        for yy in np.arange(pg[0], pg[1], .18): box(tx0 + .2, yy - .03, z + 2.95, tx1 - .3, yy + .03, z + 3.07, TEAK)
        with frame(tx1 - .75, ty1 - 2.6, z, 90): sofa(2.6, m=mat('outdoorFab', '#D8D2C6', 1., tex='weave.jpg', tile=.4), base=TEAK); seat('Terrace', LV_SF, 0, .1, .48)
        cushion(tx1 - .9, ty1 - 3.3, z + .44, PILLOW_C, rot=90); cushion(tx1 - .9, ty1 - 1.9, z + .44, PILLOW_B, rot=90)
        with frame(tx1 - 2.0, ty1 - 2.6, z, 0):
            box(-.45, -.6, .32, .45, .6, .36, TEAK, bevel=.006); box(-.4, -.55, 0, .4, .55, .32, BLACKM)
            model('wooden_bowl_01', 0, 0, .36, width=.3)
        blockrect(LV_SF, tx1 - 1.25, ty1 - 3.95, tx1, ty1 - 1.25); blockrect(LV_SF, tx1 - 2.5, ty1 - 3.25, tx1 - 1.5, ty1 - 1.95)
        rug(tx1 - 2.7, ty1 - 3.9, tx1 - 1.3, ty1 - 1.3, RUG_LOUNGE, z)
        with frame(tx0 + .8, ty1 - 1.2, z, 225):      # egg swing chair
            lathe(0, 0, 0, [(.3, 0), (.28, .03), (.05, .05)], BLACKM, 24)
            tube([(0, 0, .03), (0, 0, 1.9), (0, .25, 2.05)], .025, BLACKM)
            tube([(0, .25, 2.05), (0, .25, 1.35)], .006, BLACKM, segs=4)
            lathe(0, .25, .55, [(.05, 0), (.4, .12), (.48, .4), (.44, .7), (.25, .85), (.05, .9)], mat('rattan', '#B48A58', .8, tex='weave.jpg', tile=.15), 28)
            box(-.3, .05, .7, .3, .45, .82, LINEN_W, bevel=.05)
        blockrect(LV_SF, tx0 + .2, ty1 - 1.8, tx0 + 1.4, ty1 - .6)
        # plunge pool along the north parapet, front half
        PX0, PY0, PX1, PY1 = tx1 - 2.4, ty0 + 1.6, tx1 - .35, ty1 - 6.2
        for (a0, b0, a1, b1) in ((PX0 - .22, PY0 - .22, PX1 + .2, PY0), (PX0 - .22, PY1, PX1 + .2, PY1 + .22), (PX0 - .22, PY0, PX0, PY1), (PX1, PY0, PX1 + .2, PY1)):
            box(a0, b0, z, a1, b1, z + .5, MARBLE_V, bevel=.01)
        box(PX0, PY0, z, PX1, PY1, z + .05, mat('poolTile', '#5B9FB1', .3, tex='terrazzo_tiles', tile=.6))
        box(PX0, PY0, z + .05, PX0 + .02, PY1, z + .5, mat('poolWall', '#4E93A6', .3)); box(PX1 - .02, PY0, z + .05, PX1, PY1, z + .5, mat('poolWall', '#4E93A6', .3))
        box(PX0, PY0, z + .42, PX1, PY1, z + .43, WATER)
        for yy in np.arange(PY0 + .4, PY1, .9): box(PX0 + .02, yy - .1, z + .3, PX0 + .03, yy + .1, z + .32, LED_C)
        blockrect(LV_SF, PX0 - .25, PY0 - .25, PX1 + .25, PY1 + .25)
        for k, yy in enumerate((PY0 + .4, PY0 + 1.5)):
            with frame(PX0 - 1.1, yy, z, 0) if False else frame(tx0 + 1.3, (PY0 + PY1) / 2 + (k - .5) * 1.2, z, 90):
                box(-.95, -.32, .25, .95, .32, .32, TEAK, bevel=.01)
                with frame(.65, 0, .32, 0): box(-.3, -.3, 0, .3, .3, .06, TEAK); box(-.28, -.3, .02, .28, .3, .45, TEAK)
                box(-.9, -.29, .32, .5, .29, .4, LINEN_W, bevel=.03)
                for a in (-.85, .85):
                    for b in (-.28, .28): box(a - .03, b - .03, 0, a + .03, b + .03, .25, TEAK)
        blockrect(LV_SF, tx0 + .9, (PY0 + PY1) / 2 - 1.3, tx0 + 1.7, (PY0 + PY1) / 2 + 1.3)
        for (xx, yy, name, h) in ((tx1 - .55, ty0 + .55, 'shrub_03', 1.0), (tx1 - .55, ty1 - 5.1, 'shrub_03', 1.0), (tx0 + .5, ty0 + .55, 'shrub_03', .9)):
            box(xx - .3, yy - .3, z, xx + .3, yy + .3, z + .5, mat('planter', '#4C4844', .7), bevel=.01)
            cyl(xx, yy, z + .45, z + .48, .27, SOIL, 20)
            model(name, xx, yy, z + .47, height=h)
            blockrect(LV_SF, xx - .35, yy - .35, xx + .35, yy + .35)
        pts = [(tx0 + .3 + i * (tx1 - tx0 - .8) / 20, pg[0] - .1, z + 2.6 - .25 * math.sin(math.pi * i / 20)) for i in range(21)]
        tube(pts, .004, BLACKM, segs=4)
        for p in pts[1:-1:2]: sphere(p[0], p[1], p[2] - .05, .03, LED_C, segs=10, rings=6)
        probe('terrace', LV_SF, tx0, ty0, z, tx1, ty1, z + 4)


# ---------------------------------------------------------------- garden, compound, neighbours
def garden():
    PW, PD = X(1148), Y(15)                     # plot size (about 16.1 x 17.7 m)
    with zone('site'):     # surroundings: their own small lightmap so the house keeps the resolution
        box(-30, -30, -.3, 45, 50, -.05, mat('field', '#4F6B3A', 1., tex='lawn.jpg', tile=3.))
        box(-30, -12, -.05, 45, -2.5, -.02, mat('asphalt', '#3A3B3D', .9, tex='rough_concrete', tile=3.))   # street
        box(-30, -2.5, -.05, 45, -.2, .1, PAVER)                                                          # footpath
    with zone('ext'):
        box(0, 0, -.05, PW, PD, 0, LAWN)
        box(*R(470, 1158, 685, 1330)[:2], 0, *R(470, 1158, 685, 1330)[2:], .01, PAVER)                  # walkway
        box(X(757), 0, 0, PW, Y(862), .01, PAVER)                                                          # driveway / carport
        dx0, dy0, dx1, dy1 = R(870, 490, 1020, 835)
        box(X(RT), dy0, 0, dx1, dy1, .36, DECK)                                                            # deck
        LAYOUT['walk'].append([None, dx0, dy0, dx1, dy1, .36])
        ramp(X(RT), Y(830), dx0 + .05, Y(600), 'x', GF, .36, LV_GF, None)
        box(dx1, dy0 + .2, 0, dx1 + .3, dy1 - .2, .18, DECK); ramp(dx1, dy0 + .2, dx1 + .35, dy1 - .2, '-x', 0., .36, LV_G, None)
        for (a0, b0, a1, b1) in ((-.15, -.15, X(470), .1), (X(685), -.15, X(757) - .3, .1), (-.15, -.15, .1, PD), (PW - .1, -.15, PW + .15, PD), (-.15, PD - .1, PW + .15, PD + .15)):
            box(a0, b0, 0, a1, b1, 1.5, STONE); box(a0 - .03, b0 - .03, 1.5, a1 + .03, b1 + .03, 1.56, EXT_D)
        for xx in np.arange(X(757), PW, .12): box(xx, -.06, .05, xx + .06, .06, 1.6, BLACKM)              # vehicle gate
        for xx in (X(470), X(685)):                                                                       # open pedestrian gateway
            box(xx - .2, -.2, 0, xx + .2, .2, 1.8, STONE); box(xx - .23, -.23, 1.8, xx + .23, .23, 1.86, EXT_D)
            cyl(xx, 0, 1.86, 1.9, .08, BLACKM, 16); sphere(xx, 0, 1.98, .08, LAMP)
        for (x, y, h, c, lf, n) in ((1.3, .9, 5.0, 2.4, LEAF_P, 40),):           # one tabebuia at the gate; card trees look crude up close
            card_tree(x, y, h, c, lf, n, seed=int(x * 10 + y), avoid=[R(L, TOP, RT + 10, 862), R(L, 862, 757, FR), R(757, 865, 1140, 1240)])
        HEDGE = mat('hedge', '#FFFFFF', .9, tex='hedge.jpg', tile=.8)
        PLANTER = mat('planterStone', '#8E8A82', .8, tex='rough_concrete', tile=1.5)
        for (x, y, ax, n) in ((.45, 3.0, 'y', 2.4), (3.2, .45, 'x', 1.8), (.45, 9.0, 'y', 2.4), (.45, 14.0, 'y', 2.4),
                              (8.0, PD - .45, 'x', 2.4), (12.8, PD - .45, 'x', 2.4), (PW - .45, 12.8, 'y', 2.4)):
            hx, hy = (n / 2, .3) if ax == 'x' else (.3, n / 2)
            box(x - hx, y - hy, 0, x + hx, y + hy, .45, PLANTER, bevel=.01)                        # stone planter
            box(x - hx + .04, y - hy + .04, .45, x + hx - .04, y + hy - .04, 1.15, HEDGE, bevel=.12, seg=3)   # clipped hedge
            for s in (-1, 1):                                                                       # topiary ball at each end
                bx, by = (x + s * (hx + .35), y) if ax == 'x' else (x, y + s * (hy + .35))
                sphere(bx, by, .3, .3, HEDGE, segs=16, rings=10)
    with zone('site'):
        # neighbouring villas (same language, simple massing) and a tree line so every window has a view
        for (nx, ny, w, d) in ((-14.0, 2.3, 11.0, 13.1), (18.0, 2.3, 11.0, 13.1), (2.0, 21.0, 12.0, 13.0), (-12.0, 21.0, 11.0, 13.0), (18.0, 21.0, 11.0, 13.0)):
            box(nx, ny, 0, nx + w, ny + d, 9.8, EXT_W)
            box(nx - .3, ny - .5, 9.8, nx + w * .6, ny + d + .3, 10.15, EXT_W); box(nx - .3, ny - .5, 9.75, nx + w * .6, ny + d + .3, 9.8, TEAK)
            box(nx + 1, ny - .3, 3.5, nx + w * .7, ny, 6.8, mat('jaaliFlat', '#7A7C7C', .7))
            for zz in (3.75, 7.05): box(nx - .05, ny - .05, zz - .28, nx + w + .05, ny + d + .05, zz, EXT_D)
            for k in range(3): box(nx + 1.5 + k * 3, ny - .01, 1.0, nx + 2.7 + k * 3, ny, 2.6, mat('winDark', '#2B3238', .2, gloss=.5))
        for i in range(14):
            card_tree(-10 + i * 3.0, 36 + (i % 3), 7 + (i % 4), 3.4, LEAF_G if i % 3 else LEAF_P, 16, seed=200 + i)
        for i in range(9):
            card_tree(-8 + i * 4.0, -5.5 - (i % 2) * 1.0, 6 + (i % 3), 3.0, LEAF_G if i % 4 else LEAF_P, 16, seed=300 + i)
    with zone('ext'):
        walk(LV_G, .2, -4.8, PW - .2, PD - .2); walk(LV_G, X(470), -4.8, X(685), .3)
        blockrect(LV_G, *R(L - 5, TOP - 5, RT + 5, 862)); blockrect(LV_G, *R(L - 5, 862, 757, FR + 5))
        blockrect(LV_G, -1, -.25, X(470), .15); blockrect(LV_G, X(685), -.25, X(757), .15); blockrect(LV_G, X(757), -.25, PW + 1, .15)
        for (x, y) in ((1.6, 1.2), (15.3, 17.0), (1.4, 16.6), (14.6, 9.5)): blockrect(LV_G, x - .3, y - .3, x + .3, y + .3)
        probe('outside', LV_G, -4, -3, 0, 20, 21, 12, at=[X(575), -1.0, 1.6])


# ---------------------------------------------------------------- exterior lights (they matter at dusk)
def outdoor_lights():
    with zone('ext'):
        fy = Y(FR) - .35
        for xx in (X(130), X(470), X(640), X(745)):                      # facade uplights at the plinth
            cyl(xx, fy, 0, .03, .07, BLACKM, 16); cyl(xx, fy, .03, .032, .05, DOWN, 16)
            LIGHTS.append(('UP', (xx, fy + .05, .1), 60, .05, (1, .8, .58), 38))
        for xx in np.arange(X(890), X(1140) - .3, .9):                   # carport downlights
            spot_light(xx, (Y(875) + Y(1240)) / 2, FF - .34, 45, angle=80)
        cx0, cy0, cx1, cy1 = R(607, 930, 885, FR + 20)
        for xx in np.arange(cx0 + .6, cx1 - .3, 1.0): spot_light(xx, (cy0 + cy1) / 2, ROOF - .09, 40, angle=75)
        for (x, y) in ((.5, 5.5), (.5, 11.5), (15.6, 8.0), (15.6, 14.5), (5.0, 17.2), (11.0, 17.2), (X(1020) + .3, Y(660))):   # bollards
            cyl(x, y, 0, .012, .07, BLACKM, 20); cyl(x, y, .012, .016, .05, DOWN, 20)          # flush ground light
            LIGHTS.append(('UP', (x, y, .05), 18, .04, (1, .78, .52), 60))
        for xx in (X(470), X(685)): LIGHTS.append(('POINT', (xx, 0, 2.0), 18, .08, (1, .8, .55), 0))     # gate lamps
        LIGHTS.append(('POINT', (X(800), Y(450), SF + .25), 30, .5, (.55, .85, 1.), 0))                   # pool glow


# ---------------------------------------------------------------- build
structure(); facade(); ground_floor(); first_floor(); second_floor(); garden(); outdoor_lights()
place_plants(LVZ)
lighting(sc, SUN_AZ=30., SUN_EL=35.)
spot('Arrival', LV_G, X(578), -4.2, X(578), Y(1000), 3.5, start=True)
spot('Entrance', LV_GF, X(560), Y(1120), X(640), Y(700), 1.5)
spot('Drawing room', LV_GF, X(540), Y(1120), X(740), Y(900), 1.2)
spot('Dining', LV_GF, X(480), Y(840), X(735), Y(680), 1.0)
spot('Living', LV_GF, X(640), Y(520), X(560), Y(330), 1.4)
spot('Kitchen', LV_GF, X(480), Y(900), X(300), Y(1080), 1.1)
spot('Guest bedroom', LV_GF, X(472), Y(500), X(365), Y(250), 1.0)
spot('Deck', LV_G, X(945), Y(660), X(700), Y(400), 1.6)
spot('Staircase', LV_GF, X(480), Y(680), X(200), Y(600), 2.4)
spot('Family lounge', LV_FF, X(480), Y(780), X(820), Y(620), 1.2)
spot('Master bedroom', LV_FF, X(570), Y(510), X(455), Y(200), 1.4)
spot('Master balcony', LV_FF, X(800), Y(420), X(800), Y(150), 1.6)
spot('Bedroom 2', LV_FF, X(570), Y(900), X(410), Y(1100), 1.2)
spot('Pooja room', LV_FF, X(672), Y(830), X(667), Y(997), 1.3)
spot('Upper lobby', LV_SF, X(520), Y(820), X(520), Y(560), 1.4)
spot('Bedroom 3', LV_SF, X(570), Y(500), X(418), Y(200), 1.3)
spot('Home theatre', LV_SF, X(150), Y(870) - .6, X(105), Y(1010), 1.4) if False else spot('Home theatre', LV_SF, X(520), Y(1000), X(105), Y(1010), 1.3)
spot('Terrace', LV_SF, X(700), Y(1100), X(760), Y(300), 1.3)
spot('Plunge pool', LV_SF, X(660), Y(760), X(820), Y(1000), .6)
LAMPS = [[round(L[1][0], 3), round(L[1][1], 3), round(L[1][2], 3), L[0], *[round(c, 3) for c in L[4]]] for L in LIGHTS if L[0] in ('SPOT', 'POINT') and L[1]]
finish(sc, {'lamps': LAMPS, 'levelsZ': LVZ, 'sun': [30., 35.], 'plan': 'E350',
            'lift': {'x': X(SW1) + IT / 2 + .05, 'y': (Y(845) + Y(742)) / 2, 'out': .85, 'badgeDy': .62, 'levels': [LV_GF, LV_FF, LV_SF], 'labels': ['G', '1', '2']}})
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'villa.blend'))
print('SAVED', OUT / 'villa.blend', 'lights', len(LIGHTS))

if '--preview' in argv:
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 14; cam.data.sensor_width = 36
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.cycles.samples = 48; sc.cycles.use_denoising = True
    shots = {s['name']: ((s['x'], s['y'], LVZ[s['lv']] + 1.6), (s['lx'], s['ly'], LVZ[s['lv']] + (s['lz'] or 1.4))) for s in LAYOUT['spots']}
    shots['Aerial'] = ((X(1250), -9.0, 16.0), (X(450), Y(700), 3.0))
    want = [a for a in argv if a in shots] or ['Aerial', 'Arrival', 'Living', 'Master bedroom']
    (OUT / 'preview').mkdir(exist_ok=True)
    for n in want:
        eye, tgt = shots[n]
        cam.location = eye; cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = str(OUT / 'preview' / f'{n.replace(" ", "_")}.png'); bpy.ops.render.render(write_still=True)
        print('PREVIEW', n)
