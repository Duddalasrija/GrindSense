from math import sin, cos, pi
from pathlib import Path

OUT=Path(__file__).parent/'GrindSense_Concept'
OUT.mkdir(exist_ok=True)
class Mesh:
 def __init__(self): self.t=[]
 def tri(self,a,b,c): self.t.append((a,b,c))
 def quad(self,a,b,c,d): self.tri(a,b,c); self.tri(a,c,d)
 def cyl(self,x,y,z,r,h,n=48,r2=None):
  r2=r if r2 is None else r2
  for i in range(n):
   a=2*pi*i/n; b=2*pi*(i+1)/n
   p=(x+r*cos(a),y+r*sin(a),z); q=(x+r*cos(b),y+r*sin(b),z)
   u=(x+r2*cos(a),y+r2*sin(a),z+h); v=(x+r2*cos(b),y+r2*sin(b),z+h)
   self.quad(p,q,v,u); self.tri((x,y,z),q,p); self.tri((x,y,z+h),u,v)
 def box(self,x0,y0,z0,x1,y1,z1):
  p=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
  for ids in [(0,2,1,0,3,2),(4,5,6,4,6,7),(0,1,5,0,5,4),(1,2,6,1,6,5),(2,3,7,2,7,6),(3,0,4,3,4,7)]: self.tri(p[ids[0]],p[ids[1]],p[ids[2]]) if len(ids)==3 else (self.tri(p[ids[0]],p[ids[1]],p[ids[2]]),self.tri(p[ids[3]],p[ids[4]],p[ids[5]]))
 def blade(self,z=0):
  self.cyl(0,0,z,9,9,24)
  # four swept conceptual blades as thick tapered triangular wedges
  for angle in (0,pi/2,pi,3*pi/2):
   ux,uy=cos(angle),sin(angle); vx,vy=-uy,ux
   p=[(ux*6+vx*-5,uy*6+vy*-5,z+7),(ux*45+vx*5,uy*45+vy*5,z+7),(ux*39+vx*13,uy*39+vy*13,z+3),(ux*6+vx*5,uy*6+vy*5,z+3)]
   self.quad(*p)
   self.tri((0,0,z+4),p[0],p[1]); self.tri((0,0,z+4),p[2],p[3])
 def sphere(self,x,y,z,r,n=16,m=8):
  rings=[]
  for j in range(m+1):
   lat=-pi/2+pi*j/m
   rings.append([(x+r*cos(lat)*cos(2*pi*i/n),y+r*cos(lat)*sin(2*pi*i/n),z+r*sin(lat)) for i in range(n)])
  for j in range(m):
   for i in range(n): self.quad(rings[j][i],rings[j][(i+1)%n],rings[j+1][(i+1)%n],rings[j+1][i])
 def shifted(self,dx=0,dy=0,dz=0):
  m=Mesh(); m.t=[tuple((v[0]+dx,v[1]+dy,v[2]+dz) for v in tri) for tri in self.t]; return m
 def append(self,o): self.t.extend(o.t)
 def write(self,path,name):
  with open(path,'w') as f:
   f.write('solid '+name+'\n')
   for a,b,c in self.t:
    ux,uy,uz=b[0]-a[0],b[1]-a[1],b[2]-a[2]; vx,vy,vz=c[0]-a[0],c[1]-a[1],c[2]-a[2]
    nx,ny,nz=uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx
    l=(nx*nx+ny*ny+nz*nz)**.5 or 1; nx,ny,nz=nx/l,ny/l,nz/l
    f.write(f' facet normal {nx:.6g} {ny:.6g} {nz:.6g}\n  outer loop\n')
    for p in (a,b,c): f.write(f'   vertex {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n')
    f.write('  endloop\n endfacet\n')
   f.write('endsolid '+name+'\n')

def housing():
 m=Mesh(); m.cyl(0,0,0,55,65,64,49); m.cyl(0,0,65,49,17,64,42); m.cyl(0,0,-5,57,6,64); m.cyl(0,0,82,35,10,48)
 # front switch + feet
 m.box(-14,-53,32,14,-48,52)
 for x in (-38,38):
  for y in (-38,38): m.cyl(x,y,-9,9,5,24)
 return m
def jar(z=110):
 m=Mesh(); m.cyl(0,0,z,46,8,64); m.cyl(0,0,z+8,46,140,64,61); m.cyl(0,0,z+148,61,8,64,63); m.cyl(0,0,z+156,63,6,64)
 # faceted handle on rear, conceptual hoop-like bar
 m.box(56,39,z+35,77,53,z+126); m.box(48,39,z+25,77,53,z+42); m.box(48,39,z+119,77,53,z+136)
 return m
def lid(z=270):
 m=Mesh(); m.cyl(0,0,z,64,15,64,63); m.cyl(0,0,z+15,63,5,64,55); m.cyl(0,0,z+20,17,8,48,12); return m
def blades(z=120):
 m=Mesh(); m.blade(z); return m

def sensors():
 m=Mesh(); m.box(45,-18,25,59,18,48); m.sphere(49,0,57,7); m.box(-63,-9,45,-55,9,57); m.box(-6,52,252,6,64,264); return m
parts={'MotorHousing':housing(),'MixerJar':jar(),'BladeAssembly':blades(),'JarLid':lid(),'ProposedSensors':sensors()}
for name,m in parts.items(): m.write(OUT/(name+'.stl'),name)
assembled=Mesh()
for m in parts.values(): assembled.append(m)
assembled.write(OUT/'GrindSense_Assembled_Concept.stl','GrindSense_Assembled_Concept')
exploded=Mesh()
for name,zshift in [('MotorHousing',0),('BladeAssembly',55),('MixerJar',95),('JarLid',190),('ProposedSensors',0)]: exploded.append(parts[name].shifted(dz=zshift))
exploded.write(OUT/'GrindSense_Exploded_Concept.stl','GrindSense_Exploded_Concept')
# Standalone editable vector plate for fast submission and annotation
svg='''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000"><defs><linearGradient id="bg" x2="0" y2="1"><stop stop-color="#0c1420"/><stop offset="1" stop-color="#182638"/></linearGradient><linearGradient id="steel" x2="1" y2="1"><stop stop-color="#c7d5df"/><stop offset=".5" stop-color="#71879a"/><stop offset="1" stop-color="#34485b"/></linearGradient><linearGradient id="jar" x2="1" y2="0"><stop stop-color="#54d6cf" stop-opacity=".25"/><stop offset=".5" stop-color="#b7ffff" stop-opacity=".65"/><stop offset="1" stop-color="#39a9ae" stop-opacity=".3"/></linearGradient></defs><rect width="1600" height="1000" fill="url(#bg)"/><text x="70" y="75" fill="#f3f7fb" font-family="Arial" font-weight="700" font-size="38">GrindSense | Concept mixer-grinder</text><text x="70" y="118" fill="#9db4c9" font-family="Arial" font-size="20">Round 2 prototype • conceptual CAD visualization • dimensions illustrative, not manufacturing validated</text>
<!-- isometric body -->
<g stroke="#d8e5ee" stroke-width="3"><path fill="url(#steel)" d="M520 665 L650 590 L785 665 L785 810 L650 887 L520 810Z"/><path fill="#647d91" d="M785 665 L905 596 L905 742 L785 810Z"/><path fill="#aebfcb" d="M520 665 L650 590 L785 665 L650 740Z"/><path fill="url(#jar)" d="M540 348 L650 285 L765 348 L765 574 L650 640 L540 574Z"/><path fill="#47aeb1" fill-opacity=".65" d="M765 348 L865 291 L865 516 L765 574Z"/><path fill="#a3f3ef" fill-opacity=".5" d="M540 348 L650 285 L765 348 L650 414Z"/><path fill="#30475a" d="M535 344 L650 278 L770 343 L770 366 L650 300 L535 366Z"/><path fill="#b9c9d4" d="M520 275 L650 200 L785 275 L650 352Z"/><path fill="#74899b" d="M785 275 L820 255 L820 279 L785 299Z"/></g>
<!-- blade and sensor markers -->
<g fill="#e3eef5" stroke="#24394b" stroke-width="2"><ellipse cx="650" cy="632" rx="38" ry="14"/><path d="M650 632l-90-14 75 24zM650 632l66-46-42 56zM650 632l75 19-82-5z"/></g><g fill="#ffb44b" stroke="#fff0d5" stroke-width="3"><circle cx="827" cy="695" r="13"/><circle cx="901" cy="668" r="12"/><circle cx="849" cy="431" r="11"/><circle cx="823" cy="318" r="10"/></g>
<!-- callouts -->
<g font-family="Arial" font-size="19" fill="#f0f5f8" stroke="#93aabd" stroke-width="2"><path d="M520 742H350L300 700" fill="none"/><text x="95" y="690" stroke="none">Motor housing</text><path d="M865 400H1050L1090 360" fill="none"/><text x="1100" y="365" stroke="none">Mixer jar</text><path d="M722 636H1055L1090 600" fill="none"/><text x="1100" y="607" stroke="none">Blade assembly</text><path d="M745 241H1055L1090 215" fill="none"/><text x="1100" y="222" stroke="none">Locking lid</text><path d="M827 695H1060L1090 735" fill="none"/><text x="1100" y="743" stroke="none" fill="#ffbf62">Vibration sensor (proposed)</text><path d="M901 668H1060L1090 790" fill="none"/><text x="1100" y="800" stroke="none" fill="#ffbf62">Motor current / temperature (proposed)</text><path d="M849 431H1055L1090 440" fill="none"/><text x="1100" y="448" stroke="none" fill="#ffbf62">Jar presence interlock (proposed)</text><path d="M823 318H1055L1090 510" fill="none"/><text x="1100" y="520" stroke="none" fill="#ffbf62">Lid interlock (proposed)</text></g>
<rect x="70" y="920" width="1460" height="1" fill="#496176"/><text x="70" y="960" fill="#a6bdce" font-family="Arial" font-size="17">Concept-only geometry. No physical hardware or sensors are represented as built or tested.</text></svg>'''
(OUT/'GrindSense_Concept_Annotated.svg').write_text(svg)
print('created',len(parts),'parts; triangles',sum(len(m.t) for m in parts.values()),'assembled and exploded STL')
