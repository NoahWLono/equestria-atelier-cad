#!/usr/bin/env python3
"""Original parametric figurines. All dimensions in millimeters; no external meshes."""
import argparse, copy, json, math
from pathlib import Path
from emblems import add_emblem

ROOT=Path(__file__).resolve().parents[1]
GOLD='#D8B76B'; NAVY='#19233D'; WHITE='#FFFAF1'; INK='#202034'
CAST=[
 dict(id='twilight_sparkle',name='Twilight Sparkle',tagline='THE MAGIC OF FRIENDSHIP',body='#B299D6',mane='#343164',stripe='#ED5299',iris='#7043A1',wings=True,horn=True),
 dict(id='applejack',name='Applejack',tagline='HONEST TO THE CORE',body='#F2B45D',mane='#F7DEA0',stripe='#FCECB8',iris='#57A553',hat=True),
 dict(id='rainbow_dash',name='Rainbow Dash',tagline='CLEAR SKIES. FULL SPEED.',body='#6FC7E4',mane='#E45351',stripe='#F5C859',iris='#B64075',wings=True),
 dict(id='pinkie_pie',name='Pinkie Pie',tagline='A LITTLE EXTRA JOY',body='#F4A1C3',mane='#E7468D',stripe='#F36CAA',iris='#3CAAD3'),
 dict(id='fluttershy',name='Fluttershy',tagline='KINDNESS TAKES WING',body='#F7E8A0',mane='#F2AECA',stripe='#F9CADA',iris='#4FBAB2',wings=True),
 dict(id='rarity',name='Rarity',tagline='EVERY DETAIL MATTERS',body='#EEEAF5',mane='#7850A6',stripe='#AC8CCB',iris='#4196C1',horn=True),
 dict(id='princess_celestia',name='Princess Celestia',tagline='KEEPER OF THE DAWN',body='#FFF6ED',mane='#8BDDC1',stripe='#F4B6D1',iris='#B889BE',wings=True,horn=True,royal=True,leg_extra=8,neck_extra=10,scale=1.13),
 dict(id='princess_luna',name='Princess Luna',tagline='GUARDIAN OF THE NIGHT',body='#6E82CA',mane='#273B93',stripe='#70B9E5',iris='#64BECF',wings=True,horn=True,royal=True,leg_extra=4,neck_extra=6,scale=1.07),
 dict(id='clockwork_relativity',name='Clockwork Relativity',tagline="LUNA'S SON · TIME IN MOTION",body='#1497A5',mane='#342064',stripe='#49318D',iris='#59DB9D',horn=True,oc=True),
]

class Sculpt:
 def __init__(self,c):
  self.c=c; self.parts=[]; self.i=0
 def add(self,kind,name,color,**kw):
  self.i+=1; p=dict(kind=kind,name=f'{self.i:03d}_{name}',color=color,**kw); self.parts.append(p); return p
 def ell(self,n,c,p,r,rot=None):
  return self.add('ellipsoid',n,c,center=p,radii=r,**({'rotation':rot} if rot else {}))
 def tube(self,n,c,ps,rs):
  return self.add('tube',n,c,points=ps,radii=rs if isinstance(rs,list) else [rs]*len(ps))
 def cone(self,n,c,a,b,r1,r2):return self.add('cone',n,c,start=a,end=b,r1=r1,r2=r2)
 def cyl(self,n,c,p,r,h):return self.add('cylinder',n,c,center=p,radius=r,height=h)
 def text(self,n,c,t,p,size,depth=.6,rot=None):return self.add('text',n,c,text=t,center=p,size=size,depth=depth,**({'rotation':rot} if rot else {}))
 def poly(self,n,c,pts,o,u=[1,0,0],v=[0,0,1],d=.8):return self.add('polygon',n,c,points=pts,origin=o,u=u,v=v,depth=d)

def circle_points(center,r,n=32,plane='xy'):
 x,y,z=center
 return [(x+r*math.cos(i*2*math.pi/n),y+r*math.sin(i*2*math.pi/n),z) if plane=='xy' else (x+r*math.cos(i*2*math.pi/n),y,z+r*math.sin(i*2*math.pi/n)) for i in range(n+1)]

def eyes(s,H):
 c=s.c
 for side in [-1,1]:
  # Rounded eye layers follow the head's forward-facing cheek plane.
  theta=math.radians(-side*28)
  C=[22.0,side*9.65,H+1.4]
  def pos(u,out,v):return [C[0]+u*math.cos(theta)-side*out*math.sin(theta),C[1]+u*math.sin(theta)+side*out*math.cos(theta),C[2]+v]
  rot=[0,0,-side*28]
  s.ell(f'eye_{side}_outline',INK,pos(0,0,0),[7.15,1.25,9.0],rot)
  s.ell(f'eye_{side}_white',WHITE,pos(.12,.7,0),[6.55,1.08,8.45],rot)
  s.ell(f'eye_{side}_iris',c['iris'],pos(1.7,1.6,-.25),[3.8,.9,6.05],rot)
  s.ell(f'eye_{side}_pupil',INK,pos(2.2,2.15,-.1),[2.05,.66,4.65],rot)
  s.ell(f'eye_{side}_catchlight',WHITE,pos(1.5,2.72,2.5),[1.3,.40,1.8],rot)
  s.ell(f'eye_{side}_glint',WHITE,pos(3.0,2.65,-2.2),[.64,.34,.88],rot)
  for j in range(2 if c.get('oc') else 3):
   u=-4+j*1.6; v=6.2+(.3*j)
   s.tube(f'eyelash_{side}_{j}',INK,[pos(u,1.1,v),pos(u-1.8,1.2,v+1.3),pos(u-2.8,1.0,v+1.55)],[.48,.40,.28])
  s.ell(f'nostril_{side}',c.get('mane'),[33.3,side*5.5,H-8.0],[1.2,.52,.64],[0,0,-side*35])
  s.tube(f'smile_{side}',INK,[[32,side*6.6,H-10.6],[28.5,side*7.8,H-11.3],[24.5,side*8.2,H-10.9]],[.33,.39,.3])
  if c.get('hat'):
   for j in range(3):s.ell(f'freckle_{side}_{j}',WHITE,[24.5+j*2,side*(8.85-j*.25),H-8.3+(j%2)*1.0],[.53,.30,.53])

def wings(s,L):
 c=s.c; body=c['body']; royal=c.get('royal',False)
 for side in [-1,1]:
  if royal:
   s.tube(f'wing_{side}_leading_edge',body,[[3,side*9,42+L],[0,side*18,50+L],[-6,side*28,61+L],[-13,side*37,63+L]],[4.3,4.0,3.3,1.0])
   for j in range(7):
    a=[1-j*1.8,side*(13+j*1.7),44+L+j*1.7]
    b=[-4-j*3.1,side*(26+j*1.7),57+L-j*1.4]
    e=[-9-j*3.9,side*(33+j*1.6),60+L-j*2.6]
    s.tube(f'wing_{side}_primary_{j}',body,[a,b,e],[3.15,3.2,0.7])
   for j in range(5):
    s.tube(f'wing_{side}_covert_{j}',body,[[2-j*2.1,side*13,44+L],[-2-j*2.5,side*(21+j*.6),49+L-j*.4],[-7-j*2.5,side*(25+j*.6),50+L-j*.8]],[2.8,2.6,.65])
  else:
   # Compact folded wings keep the flank emblems visible below them.
   s.ell(f'wing_{side}_shoulder',body,[1,side*11.5,43+L],[8,3.2,7],[0,-14,0])
   for j in range(5):
    s.tube(f'wing_{side}_feather_{j}',body,[[4-j,side*11.5,45+L-j*1.0],[-3-j*1.5,side*(14.1+j*.1),44+L-j*1.0],[-13-j*1.2,side*(13.0+j*.2),43+L-j*1.5]],[2.65,2.7,.75])
   for j in range(3):s.ell(f'wing_{side}_covert_{j}',body,[0-j*3,side*14.0,45+L-j*1.3],[3.5,1.65,2.8],[0,-35,0])

def horn(s,H):
 c=s.c; royal=c.get('royal'); length=23 if royal else 14
 start=[23,0,H+11]; end=[27 if royal else 27,0,H+11+length]
 s.cone('horn',c['body'],start,end,3.4 if royal else 2.8,.48)
 pts=[]; rs=[]
 for i in range(33):
  t=.03+.86*i/32; a=t*math.pi*6; r=(3.4 if royal else 2.8)*(1-t)+.48*t
  pts.append([23+4*t+(r-.18)*math.cos(a),(r-.18)*math.sin(a),H+11+length*t]);rs.append(.39 if royal else .31)
 s.tube('horn_spiral',GOLD if c.get('royal') and c['id']=='princess_celestia' else c['body'],pts,rs)

def basic_tail(s,L):
 c=s.c; m=c['mane']; key=c['id']
 if key=='twilight_sparkle':
  path=[[-19,0,41+L],[-29,0,39+L],[-35,0,30+L],[-35,0,17],[-30,0,12]]
  s.tube('tail_mass',m,path,[6,7.5,8,7.5,3.5])
  for j,col in enumerate(['#734E9F',c['stripe']]):s.tube(f'tail_stripe_{j}',col,[[x,y-6.0+j*3.3,z+.2] for x,y,z in path],[1.2,1.8,1.9,1.8,.8])
 elif key=='applejack':
  path=[[-19,0,40+L],[-30,0,36+L],[-34,0,25],[-34,0,16]]
  s.tube('tail_ponytail',m,path,[5.4,6.7,6.0,3.4])
  s.ell('tail_red_tie','#C95255',[-34,0,18],[3.9,4,2.2])
  s.tube('tail_tuft',m,[[-34,0,17],[-36,0,12],[-30,0,9]],[3.5,5.0,.8])
  for j in [-1,1]:s.tube(f'tail_groove_{j}',c['stripe'],[[-27,j*4,37],[-33,j*5,27],[-34,j*3,20]],[.8,.75,.6])
 elif key=='rainbow_dash':
  path=[[-19,0,41],[-30,0,38],[-36,0,26],[-34,0,13],[-27,0,10]]
  s.tube('tail_mass','#7652A8',path,[6,7.4,7.4,5.8,1.0])
  cols=['#E45351','#F49B4C','#F5D766','#6FB96B','#528EC5']
  for j,col in enumerate(cols):
   y=-5.6+j*2.7
   s.tube(f'tail_rainbow_{j}',col,[[x,y,z+2.8+1.0*(2-abs(j-2))] for x,_,z in path],[1.6,2.3,2.3,1.8,.35])
 elif key=='pinkie_pie':
  path=[[-18,0,41],[-29,0,43],[-38,0,37],[-39,0,24],[-32,0,19],[-27,0,25]]
  s.tube('tail_curl',m,path,[6.5,8,8,7,5.8,2.5])
  for j,(x,y,z,sz) in enumerate([(-28,-3,42,7),(-36,-2,38,7),(-40,0,29,7),(-37,-1,21,6),(-29,-1,22,5)]):s.ell(f'tail_cloud_{j}',m,[x,y,z],[sz,6,sz])
  s.tube('tail_curl_highlight',c['stripe'],[[-29,-7,45],[-36,-7,39],[-37,-7,29],[-32,-6,25]],[.8,.9,.85,.5])
 elif key=='rarity':
  path=[[-20,0,41],[-31,0,38],[-39,0,29],[-35,0,18],[-25,0,17],[-23,0,24],[-29,0,26]]
  s.tube('tail_sculpted_curl',m,path,[6.2,7.7,7.8,7.3,5.6,3.8,1.4])
  s.tube('tail_satin_ridge',c['stripe'],[[x,-6,z+1] for x,_,z in path],[.8,1.2,1.25,1.1,.9,.65,.3])
 elif key=='fluttershy':
  path=[[-20,0,41],[-30,0,34],[-35,0,23],[-33,0,11],[-22,0,8],[-17,0,12]]
  s.tube('tail_flowing',m,path,[6,7.1,8,8,5.2,1.2])
  s.tube('tail_satin_ridge',c['stripe'],[[x,-6,z+.5] for x,_,z in path],[.8,1.0,1.15,1.1,.75,.3])
 elif c.get('royal'):
  cols=['#91DCC4','#83CCEC','#B7AAE6','#F1B8D2'] if key=='princess_celestia' else ['#273B93','#354AA8','#5677C6','#78BFE7']
  path=[[-20,0,42+L],[-33,0,39+L],[-42,0,30+L],[-44,0,18],[-34,0,10],[-25,0,13]]
  s.tube('tail_flowing_core',m,path,[6.5,8.4,9.1,9.3,6.5,1.2])
  for j,col in enumerate(cols):
   frac=-.85+j*.48
   radii=[6.5,8.4,9.1,9.3,6.5,1.2]
   locks=[[x,frac*r*.85,z+math.sqrt(1-frac*frac)*r*.85] for (x,y,z),r in zip(path,radii)]
   s.tube(f'tail_aurora_{j}',col,locks,[2.0,3,3.2,3.3,2.5,.5])
 else:
  path=[[-19,0,41],[-30,0,43],[-35,0,33],[-32,0,22],[-39,0,18],[-42,0,22]]
  s.tube('tail_oc_sweep',m,path,[6,8,7.8,7,4.8,.9])
  s.tube('tail_oc_ridge',c['stripe'],[[-24,-5,44],[-32,-6,41],[-34,-6,31],[-33,-5,24]],[1.4,1.5,1.5,.5])

def mane(s,H,L):
 c=s.c;m=c['mane'];a=c['stripe'];key=c['id']
 if key=='twilight_sparkle':
  # Fill the enclosed seam where the rounded cheek meets the fringe.
  for side in [-1,1]:s.ell(f'fringe_root_fill_{side}',c['body'],[23.5,side*8.3,H+9.43],[1.2,.75,.85])
  s.ell('mane_cap',m,[13,0,H+12],[14.8,12.7,8.6])
  # Square-ended bangs and the trademark magenta and violet ribbons.
  for j in range(6):
   y=-9+j*3.6
   s.tube(f'fringe_{j}',m,[[13,y,H+18],[23,y,H+14],[28,y,H+8]],[2.7,3.1,2.5])
  for j,col in enumerate([a,'#744B9D']):
   y=-5+j*3.5;s.tube(f'fringe_stripe_{j}',col,[[10,y,H+20.2],[20,y,H+18.1],[28,y,H+13.0],[30.0,y,H+8.6]],[1.3,1.5,1.45,.9])
  path=[[10,5,H+13],[2,6,H+3],[-2,6,H-13],[-2,5,43+L],[5,6,38+L]]
  s.tube('mane_back',m,path,[7.6,8.0,7.8,7.4,3.5])
  for j,col in enumerate([a,'#744B9D']):s.tube(f'mane_ribbon_{j}',col,[[x-7.0,y-2+j*3,z] for x,y,z in path],[1.3,1.8,2.0,1.8,.8])
 elif key=='applejack':
  s.ell('forelock_root',m,[12,0,H+11],[13,11,7])
  s.tube('forelock_sweep',m,[[15,-2,H+16],[25,-6,H+13],[26,-10,H+8],[18,-12,H+7]],[5.6,5.8,4.7,1.2])
  path=[[9,5,H+12],[1,6,H+1],[-1,7,H-12],[3,8,40+L]]
  s.tube('mane_tied',m,path,[6.6,7,6.2,3.1])
  s.ell('mane_red_tie','#C95255',[3,8,40+L],[3.7,3.9,2.2])
  s.tube('mane_tied_tuft',m,[[3,8,39+L],[8,8,34+L],[4,8,31+L]],[3.3,4.8,.8])
  s.ell('hat_brim','#B88951',[14,0,H+19],[21.5,16.5,2.4],[0,3,0])
  s.ell('hat_crown','#C39860',[12.7,0,H+23],[12.8,10,6.7],[0,3,0])
  s.ell('hat_band','#966642',[12.9,0,H+20.8],[13.2,10.3,1.1],[0,3,0])
  s.tube('hat_pinched_crease','#AC7D49',[[7,-.5,H+28.6],[12,-.5,H+29.2],[18,-.5,H+27.5]],[.5,.62,.45])
 elif key=='rainbow_dash':
  s.ell('mane_cap','#F0B552',[13,0,H+12],[14.5,12,8])
  cols=['#DE5253','#F2924A','#F2D460','#69B66D','#548EC6','#7951A9']
  for j,col in enumerate(cols[:3]):
   y=-7+j*6
   s.tube(f'rainbow_fringe_{j}',col,[[10,y,H+17],[21,y,H+16],[28,y,H+10],[24,y,H+8]],[3.4,3.8,3.1,.6])
  for j,col in enumerate(cols[3:]):
   s.tube(f'rainbow_nape_{j}',col,[[8,j*4-3,H+13],[0,j*4-3,H+4],[-2,j*4-3,H-5],[-7,j*4-3,H-8]],[3.8,4.5,4.0,.5])
  for j in range(3):s.cone(f'mane_speed_tuft_{j}',cols[j],[8-j*4,0,H+18-j],[2-j*5,0,H+24-j*3],3.5,.45)
 elif key=='pinkie_pie':
  positions=[(13,0,14,10),(21,-2,13,8),(6,-1,12,9),(0,2,4,8),(-3,3,-7,8),(-2,4,-17,8),(4,5,-23,6),(21,-7,9,6)]
  for j,(x,y,z,r) in enumerate(positions):s.ell(f'mane_curl_cloud_{j}',m,[x,y,H+z],[r,r*.85,r])
  s.tube('mane_spiral',m,[[8,-5,H+19],[17,-7,H+20],[24,-8,H+14],[19,-10,H+9],[14,-10,H+13]],[3.3,4.2,4.5,3,1.1])
  s.tube('mane_curl_highlight',a,[[2,-5,H+12],[-5,-4,H+3],[-7,-3,H-7],[-3,-3,H-16],[4,-1,H-17]],[.8,.9,1,.8,.35])
 elif key=='fluttershy':
  s.ell('mane_cap',m,[12,2,H+12],[14,12,8])
  path=[[13,0,H+16],[24,-4,H+14],[25,-8,H+10],[14,-12,H+5],[6,-13,H-7],[4,-13,H-22],[11,-12,27+L],[19,-11,29+L]]
  s.tube('mane_curtain',m,path,[5.5,6.5,6.7,6.2,6.7,6.7,5.6,1.0])
  s.tube('mane_curtain_ridge',a,[[x,y-4.9,z+1] for x,y,z in path],[.8,.9,1,1,1,.9,.7,.3])
  s.tube('mane_far_curtain',m,[[10,7,H+12],[0,8,H],[0,8,H-15],[7,8,30+L]],[5.8,6.7,6,2.2])
 elif key=='rarity':
  s.ell('mane_cap',m,[12,0,H+13],[14,12,8.5])
  path=[[12,-1,H+18],[24,-5,H+16],[26,-9,H+11],[15,-13,H+8],[2,-13,H-1],[-3,-12,H-17],[5,-14,H-23],[13,-14,H-18],[8,-14,H-14]]
  s.tube('mane_sculpted_swoop',m,path,[5.8,6.2,5.9,5.6,6.5,6.5,5.7,3.4,1.0])
  s.tube('mane_satin_ridge',a,[[x,y-4.9,z+1] for x,y,z in path],[.8,1.0,1.05,1.0,1.1,1.1,.9,.65,.3])
  s.tube('mane_far_lock',m,[[10,7,H+11],[1,8,H],[0,8,H-15],[7,8,H-19]],[5.2,6,5,1.2])
 elif c.get('royal'):
  cols=['#8BDDC1','#88CEEB','#B2A1E0','#F0B4D1'] if key=='princess_celestia' else ['#273B93','#354BA9','#5478C6','#7BBCE7']
  s.ell('mane_crown_sweep',m,[11,0,H+12],[14.2,12,7.5])
  path=[[13,-2,H+15],[5,-7,H+12],[-4,-10,H+2],[-13,-12,H-8],[-14,-13,H-24],[-6,-15,35+L],[7,-16,30+L]]
  s.tube('mane_aurora_core',m,path,[6.2,8,9.5,10.0,10.0,8,2])
  for j,col in enumerate(cols):
   # Parallel sculpted locks drape down the neck in a four-color wave.
   frac=-.85+j*.48
   radii=[6.2,8,9.5,10.0,10.0,8,2]
   locks=[[x,y+frac*r*.85,z+math.sqrt(1-frac*frac)*r*.85] for (x,y,z),r in zip(path,radii)]
   s.tube(f'mane_aurora_lock_{j}',col,locks,[2,2.9,3.4,3.6,3.6,3,0.7])
  s.tube('royal_forelock',cols[-1],[[13,0,H+17],[24,-3,H+13],[25,-8,H+9],[20,-11,H+9]],[3.9,4.2,3.5,.65])
  if key=='princess_luna':
   for j,(x,y,z) in enumerate([(-8,-20,H-4),(-13,-21,H-15),(-10,-22,H-26),(0,-22,36+L)]):s.ell(f'mane_starlight_{j}',WHITE,[x,y,z],[.75,.45,.75])
 else:
  # Clockwork: tousled violet silhouette and cheek-length locks, per supplied sprite.
  s.ell('oc_mane_cap',m,[13,0,H+12],[15.0,12.4,9])
  for j,(x,y,z,dx,dz) in enumerate([(22,-5,13,8,2),(16,-7,17,4,9),(8,-2,18,-2,9),(2,1,13,-7,3),(18,5,17,2,7)]):
   s.tube(f'oc_mane_spike_{j}',m,[[x,y,H+z-4],[x+dx*.5,y,H+z],[x+dx,y,H+z+dz]],[4.6,4.4,.45])
  s.tube('oc_sideburn_near',m,[[8,-9,H+10],[5,-12,H+1],[8,-12,H-5]],[5.2,4.6,.7])
  s.tube('oc_nape',m,[[9,6,H+12],[1,8,H+1],[0,9,H-13],[6,9,H-17]],[6.4,6.6,5.6,.8])
  s.tube('oc_mane_ridge',a,[[10,-10,H+18],[20,-12,H+15],[23,-12,H+10]],[.9,1.2,.5])

def regalia(s,H,L):
 c=s.c;sun=c['id']=='princess_celestia'; metal=GOLD if sun else '#263560';gem='#AA77CD' if sun else '#A1DEEA'
 # Broad collar joins the chest and carries a raised centerpiece.
 s.ell('royal_collar',metal,[12,0,50+L],[10.5,9.5,4.2],[0,-16,0])
 s.ell('collar_gem',gem,[22,0,52+L],[1.3,3.7,3.4],[0,-16,0])
 s.ell('crown_band',metal,[14,0,H+19],[10.5,10.2,1.6])
 for y in [-7,0,7]:
  s.cone(f'crown_point_{y}',metal,[18,y,H+18],[18.5,y,H+27-(2 if y else 0)],2.8,.5)
 s.ell('crown_jewel',gem,[20.1,0,H+22],[1.0,2.0,2.7])
 for x in [-14,13]:
  for side in [-1,1]:
   s.ell(f'royal_shoe_{x}_{side}',metal,[x+.7,side*7.7,8],[6.6,4.9,3.3])
   s.ell(f'royal_shoe_gem_{x}_{side}',gem,[x+4,side*10.3,8.8],[1.6,.65,1.3])

def build(c):
 s=Sculpt(c);B=c['body'];L=c.get('leg_extra',0);N=c.get('neck_extra',0);H=65+L+N
 radius=47 if c.get('royal') else 43
 s.cyl('plinth_foot',NAVY,[0,0,0],radius,3.5)
 s.cyl('plinth_gold_reveal',GOLD,[0,0,3.0],radius-.35,1.1)
 s.cyl('plinth_top',NAVY,[0,0,3.7],radius-1.2,1.6)
 # Name follows the front rim; text lies on the horizontal top.
 label=c['name'].upper().replace('PRINCESS ','')
 s.text('plinth_name',GOLD,label,[27.5,0,5.15],3.0 if len(label)<20 else 2.4,.55,[0,0,90])
 s.ell('barrel',B,[-2,0,37+L],[21,11.8,14.0])
 s.ell('rump',B,[-14,0,36+L],[12.2,12.4,13.6])
 s.ell('chest',B,[11,0,40+L],[10.7,10.7,14.2],[0,16,0])
 s.ell('neck',B,[12,0,48+L+N*.48],[9.5,9,16+N*.65],[0,12,0])
 for x in [-14,13]:
  for side in [-1,1]:
   y=side*7.7
   s.tube(f'leg_{x}_{side}',B,[[x,y,36+L],[x-1 if x<0 else x+1,y,23+L*.5],[x+.7,y,9]],[5.5,3.9,5.4])
   s.ell(f'hoof_{x}_{side}',B,[x+1.2,y,8],[6.2,4.7,3.1])
   if c.get('oc'):
    s.ell(f'oc_purple_hoof_{x}_{side}',c['mane'],[x+1.2,y,6.9],[6.25,4.75,1.9])
    for j in range(3):s.ell(f'oc_hoof_fetlock_{x}_{side}_{j}',B,[x-2+j*2.7,y+side*3.7,8.7],[1.3,1.4,1.8])
 s.ell('head',B,[15,0,H],[16,12.8,17])
 s.ell('muzzle',B,[27,0,H-7.6],[10,9.2,7.2])
 for side in [-1,1]:
  s.ell(f'ear_{side}',B,[13,side*8.0,H+15.2],[4.3,3.6,9.0],[side*18,-10,0])
  s.ell(f'ear_inner_{side}',c['mane'] if c.get('oc') else '#DEB3BE',[15.5,side*9.0,H+17.3],[1.3,2.0,5.2],[side*18,-10,0])
 eyes(s,H)
 basic_tail(s,L)
 if c.get('wings'):wings(s,L)
 mane(s,H,L)
 if c.get('horn'):horn(s,H)
 if c.get('royal'):regalia(s,H,L)
 for side in [-1,1]:
  i=len(s.parts);add_emblem(s.parts,c['id'],[-14,side*12.3,34.5+L],.89,side)
  s.parts[i]['color']=B
  # Prefix helper-generated names consistently and uniquely.
  for j,p in enumerate(s.parts[i:]):p['name']=f'emblem_{side}_{j}_{p["name"]}'
 scale=c.get('scale',1)
 if scale!=1:
  for p in s.parts:
   for k in ['center','start','end','origin','radii']:
    if k in p:p[k]=[v*scale for v in p[k]]
   if p['kind']=='tube':p['points']=[[v*scale for v in pt] for pt in p['points']]
   if p['kind']=='polygon':p['points']=[[v*scale for v in pt] for pt in p['points']]
   for k in ['radius','height','depth','r1','r2','size']:
    if k in p:p[k]*=scale
 return dict(id=c['id'],name=c['name'],tagline=c['tagline'],parts=s.parts,design=dict(body=B,mane=c['mane'],iris=c['iris'],scale=scale,style='Original stylized collectible',species='alicorn' if c.get('wings') and c.get('horn') else 'pegasus' if c.get('wings') else 'unicorn' if c.get('horn') else 'earth pony'))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'outputs/collection.json');args=parser.parse_args()
 chars=[build(c) for c in CAST]
 doc=dict(title='EQUESTRIA · ATELIER COLLECTION',version='1.0',units='mm',characters=chars)
 args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(doc,indent=2)+'\n')
 print(f'Wrote {len(chars)} characters / {sum(len(c["parts"]) for c in chars)} CAD components to {args.out}')
 for c in chars:print(c['id'],len(c['parts']))
if __name__=='__main__':main()
