#!/usr/bin/env python3
"""Create checksum-verified delivery archives after full collection validation."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs';DIST=ROOT/'deliverables'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def zip_checked(name,paths,prefix):
 target=DIST/name
 mapping={prefix+'/'+str(p.relative_to(ROOT)):p for p in paths}
 sums=''.join(f'{sha(p)}  {n}\n' for n,p in sorted(mapping.items()))
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,path in sorted(mapping.items()):z.write(path,name)
  z.writestr(prefix+'/SHA256SUMS.txt',sums)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  for name,path in mapping.items():assert hashlib.sha256(z.read(name)).hexdigest()==sha(path)
 print(target,round(target.stat().st_size/1048576,1),'MiB',len(paths),'files',flush=True)
 return dict(file=target.name,sha256=sha(target),bytes=target.stat().st_size,files=len(paths),archive_crc_and_sha256_verified=True)
def main():
 validation=json.loads((OUT/'reports/verification.json').read_text())
 assert validation['status']=='passed' and len(validation['characters'])==9 and not validation['geometry_only'],'Run full verification first'
 DIST.mkdir(exist_ok=True)
 ids=[c['id'] for c in validation['characters']]
 dimensions=['# Model dimensions', '', 'Dimensions include the integrated plinth. CAD and STL coordinates use millimeters.', '', '| Figure | Length X (mm) | Width Y (mm) | Height Z (mm) | CAD components |', '|---|---:|---:|---:|---:|']
 for c in validation['characters']:
  x,y,z=c['extents_mm'];dimensions.append(f"| {c['name']} | {x:.2f} | {y:.2f} | {z:.2f} | {c['cad_components']} |")
 (OUT/'DIMENSIONS.md').write_text('\n'.join(dimensions)+'\n')
 files=[ROOT/'README.md',ROOT/'build.sh',ROOT/'requirements.txt',OUT/'collection.json',OUT/'collection.blend',OUT/'DIMENSIONS.md']
 for folder in ['source','docs','assets','references']:
  files += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
 for folder in ['step','stl','color','renders','previews']:
  files += [p for p in (OUT/folder).rglob('*') if p.is_file() and p.suffix.lower() in ['.step','.stl','.glb','.png','.jpg','.svg']]
 report_paths=[OUT/'reports'/f'{key}.json' for key in ids]
 report_paths += [OUT/'reports'/n for n in ['verification.json','catalog.json','blend.json','emblem_geometry.json']]
 report_paths += list((OUT/'reports/renders').glob('*.json'))
 files+=report_paths
 files=sorted(set(files))
 (OUT/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in files))
 results=[zip_checked('Equestria-Atelier-Complete-9-Figure-Set.zip',files,'Equestria-Atelier'),zip_checked('Equestria-Atelier-STEP-CAD.zip',[OUT/'step'/f'{i}.step' for i in ids]+[OUT/'DIMENSIONS.md']+report_paths[:9],'Equestria-STEP'),zip_checked('Equestria-Atelier-STL-Print-Meshes.zip',[OUT/'stl'/f'{i}.stl' for i in ids]+[ROOT/'docs/printing-and-editing.md']+report_paths[:9],'Equestria-STL')]
 (DIST/'archives.json').write_text(json.dumps(results,indent=2)+'\n')
 (DIST/'SHA256SUMS.txt').write_text(''.join(f'{r["sha256"]}  {r["file"]}\n' for r in results))
if __name__=='__main__':main()
