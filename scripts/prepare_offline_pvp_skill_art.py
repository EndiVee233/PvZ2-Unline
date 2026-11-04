"""Repair imported 640 art geometry and resize the four PvP ground effects."""
from pathlib import Path
from io import BytesIO
import hashlib,json,struct,zlib
from merge_legacy_pvp_resources import Bundle,u32,trie_write
from pam_transform_index import PamIndex

def patch_pam(raw,low_resolution,phase_scale=None):
 index=PamIndex(raw);edits=[]
 if low_resolution:
  # Atlas pixels are 640 assets selected as 1536: normalize the image basis,
  # not the bone positions. Frame translations and all animation commands stay.
  for image in index.images:
   off=image['off']+4;values=struct.unpack_from('<4i',raw,off)
   edits.append((off,off+16,struct.pack('<4i',*(round(v*1536/640) for v in values))))
 root=index.sprites[-1];changed_moves=0
 if phase_scale:
  sx,sy,px,py,dx,dy,label=phase_scale;active=False
  for frame in root['frames']:
   if frame['label']:active=frame['label']==label
   if not active:continue
   for move in frame['moves']:
    start,end=move['start'],move['end'];flags=move['flags'];pos=start+2
    prefix=raw[start+2:start+6] if flags&1023==1023 else b'';pos+=len(prefix)
    if flags&4096:
     a,c,b,d=struct.unpack_from('<4i',raw,pos);a/=65536;c/=65536;b/=65536;d/=65536;pos+=16
    elif flags&16384:
     # Keep rotation as a complete matrix before applying anisotropic scaling.
     import math
     angle=struct.unpack_from('<h',raw,pos)[0]/1000;pos+=2
     a=d=math.cos(angle);b=-math.sin(angle);c=-b
    else:a=d=1.;b=c=0.
    x,y=move['pos'];pos+=8 if flags&2048 else 4
    x=round((px+sx*(x/20-px)+dx)*20);y=round((py+sy*(y/20-py)+dy)*20)
    replacement=struct.pack('<H',((flags|4096|2048)&~16384))+prefix
    replacement+=struct.pack('<4i2i',round(sx*a*65536),round(sy*c*65536),round(sx*b*65536),round(sy*d*65536),x,y)
    replacement+=raw[pos:end];edits.append((start,end,replacement));changed_moves+=1
 result=bytearray(raw)
 for start,end,value in sorted(edits,reverse=True):result[start:end]=value
 check=PamIndex(bytes(result))
 assert len(check.images)==len(index.images) and len(check.sprites)==len(index.sprites)
 for old,new in zip(index.sprites,check.sprites):
  assert old['name']==new['name'] and len(old['frames'])==len(new['frames'])
  for a,b in zip(old['frames'],new['frames']):
   assert (a['label'],a['commands'],a['adds'],a['rem'])==(b['label'],b['commands'],b['adds'],b['rem'])
 return bytes(result),dict(image_bases_normalized=len(index.images) if low_resolution else 0,ground_moves_rescaled=changed_moves)

def prepare(resource,out):
 bundle=Bundle(resource);changes=[]
 for i,g in enumerate(bundle.groups):
  if not g['ID'].startswith(('ZombiePVPSkillAidGroup_Common','ZombiePVPSkillInvisibleGroup_Common','ZombiePVPSkillZombieFoodGroup_Common','ZombiePVPSkillRageGroup_Common')):continue
  old=bundle.payloads[i];off=u32(old,24);section=old[off:off+u32(old,28)]
  if u32(old,16)&2:section=zlib.decompress(section)
  entries=list(bundle.files(i));changed=False
  for j,(name,info) in enumerate(entries):
   if not name.endswith('.PAM'):continue
   low='\\640\\' in name;phase=None
   if name.endswith('\\ZOMBIE_PVPSKILL_AID.PAM'):phase=(4/3,4/3,223.5,227.5,-50,-50,'idle')
   elif '\\ZOMBIE\\' in name and name.endswith('\\ZOMBIE_PVPSKILL_RAGE.PAM'):phase=(5/3,4/3,226.3,234.7,0,-50,'idle')
   elif '\\EFFECTS\\' in name and name.endswith('\\ZOMBIE_PVPSKILL_ZOMBIEFOOD.PAM'):phase=(1.25,1.25,192,220,0,0,'idle1')
   if not low and not phase:continue
   raw=section[info[1]:info[1]+info[2]];new,record=patch_pam(raw,low,phase)
   entries[j]=(name,(0,len(section),len(new)));section+=new;changed=True
   changes.append(dict(name=name,sha256_before=hashlib.sha256(raw).hexdigest(),sha256_after=hashlib.sha256(new).hexdigest(),phase=phase,**record))
  if not changed:continue
  section+=bytes((-len(section))%4096);head=bytearray(old[:off]);table=trie_write(entries,1);at=u32(head,0x4c);assert at+len(table)<=off
  head[at:at+len(table)]=table;struct.pack_into('<I',head,0x48,len(table));struct.pack_into('<I',head,16,u32(head,16)&~2)
  struct.pack_into('<II',head,28,len(section),len(section));struct.pack_into('<I',head,40,len(head)+len(section))
  textures=old[u32(old,40):u32(old,40)+u32(old,44)];bundle.payloads[i]=head+section+textures;bundle.sync_info(i)
 assert len(changes)==5,changes
 result=bundle.build();check=Bundle(result)
 assert check.manifest()[2]==bundle.manifest()[2]
 for i in range(len(bundle.groups)):assert check.payloads[i]==bundle.payloads[i]
 record=dict(changes=changes,predecessor_sha256=hashlib.sha256(resource).hexdigest(),sha256=hashlib.sha256(result).hexdigest(),size=len(result),atlas_pixels_unchanged=True,animation_events_preserved=True)
 out=Path(out);(out/'zombie2-skill-art.rsb.smf').write_bytes(result);(out/'skill-art-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return result,record
