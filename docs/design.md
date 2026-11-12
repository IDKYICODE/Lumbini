# Lumbini Vana villa – VR walkthrough (proof of concept)

Updated 2026-11-12. Status: built; first full bake done; awaiting phone test.

## Scope
One villa, end to end: facade, entrance, carport, its garden, three floors inside, the terrace. Not the colony,
clubhouse or amenities (user's instruction).

## Source
- Plan: the **350 sq yd East-facing villa** from the Vana brochure (vana.lumbini.com/floor-plans, page 14),
  G+2, built-up 1772 + 1625 + 1081 = 4478 sq ft, plot about 16.1 x 17.7 m. Saved in `refs/brochure/`.
- Look: the Vana film (`refs/video/villa.mp4`, contact sheets `refs/sheets/`) and the brochure elevations.

## Rooms (as on the brochure plan)
| Floor | Rooms |
|---|---|
| Ground (+0.45) | Entrance steps, drawing room, dining, living (TV wall), guest bedroom + walk-in + toilet, kitchen + store + utility, maid room + toilet, powder room, lift, U stair, side deck, carport |
| First (+3.75) | Family lounge, master bedroom + walk-in + toilet + balcony, bedroom 2 + walk-in + toilet + balcony (behind the jaali), pooja room, lift |
| Second (+7.05) | Lobby, bedroom 3 + walk-in + toilet, powder room, home theatre (3 tiers of recliners), terrace with pergola lounge, plunge pool, loungers, swing chair |

Toilets, store, utility and the maid room stay behind closed doors in this slice.

## Design decisions (mine, from the film; to confirm with the client)
- Facade: white render, charcoal slab bands, grey jaali box with triangular cut-outs around bedroom 2 and its
  balcony, teak door surround, stone cladding, grey fluting, flat roof with teak soffits and a canopy over the
  terrace, carport roof with a teak soffit on slim black columns.
- Inside: white statuario marble (ground, lounge, lobby), oak floors in bedrooms, boucle sofas, navy velvet dining
  chairs, walnut joinery with bronze glass, gypsum cove ceilings with warm LED and downlights, brass linear pendant,
  fluted headboard walls, sage velvet accents, chinoiserie mural in the lounge, pooja room with marble and brass,
  dark fluted theatre with a star ceiling.
- Light: morning sun from the east (front), as in "ground floor mornings"; an evening (dusk) mood with every lamp,
  cove, facade uplight and bollard on, as in "where coming home feels different". A plunge pool on the terrace is our addition.

## Rendering approach
- Built procedurally in Blender 4.4 (`blender/`), headless; plan entered in brochure pixels so it is easy to correct.
- Real materials (Poly Haven CC0 + generated), world-scale UVs on channel 0.
- Lighting baked in Cycles per zone (garden/facade, surroundings, ground, first, second) into lightmaps on UV channel 1,
  two moods, OIDN denoised, sRGB-encoded 8-bit with a per-zone scale.
- Viewer: unlit materials + lightmap + AgX tone mapping; glossy surfaces get box-projected reflection probes
  (one per room) captured at load; leaves sway, the pool shimmers, the clouds drift.
- Movement from office-vr plus: three levels, walkable stairs, a working lift, a guided next/previous room, a 2D
  line-of-sight check so only rings in the same room show.

## Budget (phone)
About 25–35 MB download, 2048 px lightmaps on phones, floors two levels away are not drawn.
