"""Download the CC0 Poly Haven assets the villa uses into assets_src/ (skips files already there).

python tools/fetch_assets.py
"""
import json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'assets_src'
UA = {'User-Agent': 'villa-walkthrough-poc'}

TEXTURES = {   # name: resolution
    'marble_01': '2k', 'walnut_veneer': '2k', 'teak_veneer': '2k', 'oak_veneer_01': '2k', 'wood_floor': '2k',
    'white_plaster_02': '1k', 'granite_tile': '2k', 'brown_leather': '1k', 'wood_floor_deck': '2k',
    'concrete_pavers': '2k', 'leafy_grass': '2k', 'stone_tile_wall': '2k', 'terrazzo_tiles': '2k',
    'rough_concrete': '1k', 'patterned_paving': '2k',
}
MODELS = ['anthurium_botany_01', 'calathea_orbifolia_01', 'fern_02', 'potted_plant_01', 'Chandelier_02',
          'modern_ceiling_lamp_01', 'brass_diya_lantern', 'ceramic_vase_01', 'ceramic_vase_03', 'brass_vase_01',
          'brass_vase_03', 'throw_pillows_01', 'tea_set_01', 'shrub_01', 'shrub_03', 'brass_pot_01',
          'wooden_bowl_01', 'antique_ceramic_vase_01', 'pachira_aquatica_01', 'potted_plant_02', 'potted_plant_04',
          'shrub_sorrel_01', 'shrub_02']
HDRIS = {'kloofendal_48d_partly_cloudy_puresky': '4k'}


def get(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0: return
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r: dest.write_bytes(r.read())
    print('  ', dest.relative_to(ROOT))


def files(asset):
    with urllib.request.urlopen(urllib.request.Request(f'https://api.polyhaven.com/files/{asset}', headers=UA)) as r:
        return json.load(r)


for name, res in TEXTURES.items():
    f = files(name)
    for kind in ('Diffuse', 'Rough'):
        if kind in f: get(f[kind][res]['jpg']['url'], ROOT / 'tex' / name / f'{kind.lower()}.jpg')
    print('tex', name)
for name in MODELS:
    g = files(name)['gltf']['1k']['gltf']
    get(g['url'], ROOT / 'models' / name / Path(g['url']).name)
    for rel, v in g.get('include', {}).items(): get(v['url'], ROOT / 'models' / name / rel)
    print('model', name)
for name, res in HDRIS.items():
    get(files(name)['hdri'][res]['hdr']['url'], ROOT / 'hdri' / f'{name}.hdr')
    print('hdri', name)
