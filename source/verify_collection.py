#!/usr/bin/env python3
"""Independently inspect the delivered files and bind them to the editable design."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image
from export_cad import cq
from design import CAST, build

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)

def check(c,full):
 key=c['id'];report=json.loads((OUT/'reports'/f'{key}.json').read_text())
 require(report['status']=='passed',key+': export report failed')
 expected=hashlib.sha256(json.dumps(c,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 require(report.get('design_sha256')==expected,key+': report belongs to a different design')
 stl=OUT/'stl'/f'{key}.stl'; step=OUT/'step'/f'{key}.step';glb=OUT/'color'/f'{key}.glb'
 mesh=trimesh.load(stl,force='mesh')
 shells=mesh.split(only_watertight=False)
 require(mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume,key+': STL is not a positive closed solid')
 require(len(shells)==1,key+': disconnected STL')
 require(mesh.bounds[0,2]>=-.01,key+': geometry below build plate')
 require(np.allclose(mesh.extents,report['stl_import']['extents_mm'],atol=1e-4),key+': saved STL dimensions changed')
 scene=trimesh.load(glb,force='scene')
 require(set(scene.geometry)=={p['name'] for p in c['parts']},key+': GLB component names changed')
 expected_bounds=np.array([[mesh.bounds[0,0],mesh.bounds[0,2],-mesh.bounds[1,1]],[mesh.bounds[1,0],mesh.bounds[1,2],-mesh.bounds[0,1]]])/1000
 require(np.allclose(scene.bounds,expected_bounds,atol=.00006),key+': GLB 3D bounds disagree with STL')
 imported=cq.Compound.makeCompound(cq.importers.importStep(str(step)).vals())
 solids=imported.Solids()
 require(imported.isValid() and len(solids)==report['cad']['solid_count'] and all(x.isValid() and x.Volume()>0 for x in solids),key+': invalid STEP roundtrip')
 hashes={fmt:digest(path) for fmt,path in [('stl',stl),('step',step),('glb',glb)]}
 for fmt,h in hashes.items():require(report['output_sha256'].get(fmt)==h,key+': export '+fmt+' hash changed')
 if full:
  render=OUT/'renders'/f'{key}.png';rp=json.loads((OUT/'reports/renders'/f'{key}.json').read_text())
  with Image.open(render) as im:require(im.size==(1200,1400),key+': full-resolution render missing');im.verify()
  require(rp['sha256']==digest(render),key+': render image changed')
  require(rp['sources'][0]['sha256']==hashes['glb'],key+': render belongs to a different GLB')
  for view in ['front','side','back']:
   ortho=OUT/'renders/orthographic'/f'{key}_{view}.png'
   require(ortho.is_file(),key+': missing '+view+' view')
   verify_render(ortho)
 return dict(id=key,name=c['name'],status='passed',cad_components=len(c['parts']),cad_solids=len(solids),stl_triangles=len(mesh.faces),extents_mm=[round(float(x),3) for x in mesh.extents],volume_mm3=round(float(mesh.volume),3),watertight=True,connected_shells=1,design_sha256=expected,sha256=hashes)

def verify_render(path):
 rp=json.loads((OUT/'reports/renders'/(path.stem+'.json')).read_text())
 require(rp['sha256']==digest(path),str(path)+': render hash mismatch')
 with Image.open(path) as im:
  require(list(im.size)==rp['resolution'],str(path)+': render dimensions mismatch');im.verify()
 for src in rp['sources']:
  require(digest(OUT/'color'/(src['id']+'.glb'))==src['sha256'],str(path)+': stale render source')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--geometry-only',action='store_true');args=parser.parse_args()
 data=json.loads((OUT/'collection.json').read_text());chars=data['characters']
 require(data.get('units')=='mm','CAD collection units must be mm')
 require(chars==[build(c) for c in CAST],'Editable Python source differs from collection.json; regenerate it')
 required={'twilight_sparkle','applejack','rainbow_dash','pinkie_pie','fluttershy','rarity','princess_celestia','princess_luna','clockwork_relativity'}
 require({c['id'] for c in chars}==required and len(chars)==9,'Collection must contain all nine distinct figures')
 results=[];failures=[]
 for c in chars:
  try:
   item=check(c,not args.geometry_only);results.append(item)
   print(f"PASS {c['id']}: {item['cad_components']} CAD components, {item['stl_triangles']:,} triangles, {item['extents_mm'][2]:.2f} mm high",flush=True)
  except Exception as e:failures.append(dict(id=c['id'],error=str(e)));print('FAIL',c['id'],str(e),flush=True)
 if not args.geometry_only and not failures:
  for rel in ['renders/collection_catalog.png','renders/collection_hero.png','renders/luna_and_clockwork_plate.png','collection.blend']:
   if not (OUT/rel).is_file():failures.append(dict(file=rel,error='Missing deliverable'))
  try:
   verify_render(OUT/'renders/full_cast.png');verify_render(OUT/'renders/luna_and_clockwork.png')
   catalog=json.loads((OUT/'reports/catalog.json').read_text())
   for record in [catalog['collection']]+catalog['sources']+catalog['outputs']:
    require(digest(OUT/record['file'])==record['sha256'],'Catalog has a stale source/output: '+record['file'])
   blend=json.loads((OUT/'reports/blend.json').read_text())
   require(digest(ROOT/blend['file'])==blend['sha256'],'Blender scene hash mismatch')
   require(blend['character_count']==9 and blend['readback_verified'],'Blender scene readback failed')
   require({x['id'] for x in blend['characters']}==required,'Blender scene missing characters')
   for record in blend['characters']:require(digest(ROOT/record['file'])==record['sha256'],'Blender scene has a stale character')
  except Exception as e:failures.append(dict(file='presentation_assets',error=str(e)))
 verification=dict(status='passed' if not failures else 'failed',characters=results,failures=failures,geometry_only=args.geometry_only,physical_print_tested=False)
 (OUT/'reports/verification.json').write_text(json.dumps(verification,indent=2)+'\n')
 print(f'{len(results)}/9 character files verified; {len(failures)} failure(s).',flush=True)
 return 1 if failures else 0
if __name__=='__main__':sys.exit(main())
