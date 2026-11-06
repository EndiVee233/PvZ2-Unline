"""Fixed-roster shop rearrangement: keep all plants and save positions only."""
from check_offline_pvp_v81_arm import GarrisonEngine,OUT,claim
from check_offline_pvp_v80_arm import check_capture
from check_offline_pvp_v79_arm import check_scout,check_ownership,check_businesses
from check_offline_pvp_arm import M,PM
from check_offline_pvp_v56_arm import BOARD
import struct,json

def set_positions(e,rows):
 p=e.alloc(len(rows)*12) if rows else 0
 if rows:e.u.mem_write(p,b''.join(struct.pack('<III',*r) for r in rows))
 e.put(M+0x84,p);e.put(M+0x88,p+len(rows)*12);e.put(M+0x8c,p+len(rows)*12)

def positions(e):return [struct.unpack('<III',e.plants()[i:i+12]) for i in range(0,len(e.plants()),12)]
def checksum(raw,skip):
 h=2166136261
 for i,c in enumerate(raw):
  if not skip<=i<skip+4:h=((h^c)*16777619)&0xffffffff
 return h

def check_reposition():
 e=GarrisonEngine();e.enter();e.run('offlineGarden');assert e.edit(0)==0
 for _ in range(3):e.train()
 e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20));claim(e,0);claim(e,1)
 e.own();e.arrangement(2,0,8);e.save();e.request(3)
 home=next(k for k in e.files if k.endswith('.def'));home_bytes=bytes(e.files[home])
 funds=(e.get(M+4),e.get(M+8),e.gems,e.held(),e.owned())
 assert e.edit(0)==1 and positions(e)==[(2,r,0) for r in range(5)]
 assert e.get(M+0xa8)==2,'shop left the native fixed-roster drag mode'
 original=positions(e);moved=list(original);moved[0]=(2,0,4);set_positions(e,moved)
 assert e.edit(0)==0 and positions(e)==moved,'duplicate entry discarded drag changes'
 e.save();assert e.get(BOARD+0xc0)==9;e.request(3)
 one=next(k for k in e.files if k.endswith('-shop-71000001.def'));saved_one=bytes(e.files[one])
 assert e.edit(0)==1 and positions(e)==moved
 unsaved=list(moved);unsaved[1]=(2,1,6);set_positions(e,unsaved);e.request(3)
 assert e.edit(0)==1 and positions(e)==moved,'discarded rearrangement persisted'
 # No deletion, insertion, substitution or overlapping cells can be saved.
 bad=[moved[:-1],moved+[(2,4,8)],[(3,*moved[0][1:])]+moved[1:],[],[moved[0],moved[0]]+moved[2:]]
 for rows in bad:
  set_positions(e,rows);before=len(e.scenes);e.save()
  assert bytes(e.files[one])==saved_one and len(e.scenes)==before and e.get(BOARD+0xc0)==5
 # Reordering serialized entries is allowed; plant multiset stays the same.
 set_positions(e,list(reversed(unsaved)));e.failwrite=True;e.save()
 assert bytes(e.files[one])==saved_one and e.get(BOARD+0xc0)==5
 e.failwrite=False;e.save();e.request(3)
 assert e.edit(0)==1 and positions(e)==list(reversed(unsaved));e.request(3)
 assert e.edit(1)==1 and positions(e)==[(6,r,0) for r in range(5)]
 second=positions(e);second[4]=(6,4,7);set_positions(e,second);e.save();e.request(3)
 two=next(k for k in e.files if k.endswith('-shop-71000002.def'))
 assert bytes(e.files[home])==home_bytes and (e.get(M+4),e.get(M+8),e.gems,e.held(),e.owned())==funds
 r=GarrisonEngine();r.copy_state(e);r.enter();r.run('offlineGarden')
 assert r.edit(0)==1 and positions(r)==list(reversed(unsaved));r.request(3)
 assert r.edit(1)==1 and positions(r)==second;r.request(3)
 r.own();assert positions(r)==[(2,0,8)];r.request(3)
 # Wrong-shop/corrupt envelopes remain errors, never replaced with defaults.
 original_file=bytes(r.files[one]);r.files[one]=bytearray(r.files[two]);before=r.own_loads
 assert r.edit(0)==0 and r.own_loads==before
 r.files[one]=bytearray(original_file);r.files[one][100]^=1;assert r.edit(0)==0
 # A valid v81 empty save is repaired in memory; opening alone never writes.
 raw=bytearray(original_file);struct.pack_into('<II',raw,32,0,0)
 struct.pack_into('<I',raw,40,checksum(raw[20:],20));struct.pack_into('<I',raw,16,checksum(raw,16))
 r.files[one]=raw;before=bytes(raw);assert r.edit(0)==1
 assert positions(r)==[(2,row,0) for row in range(5)] and bytes(r.files[one])==before
 restored=positions(r);restored[0]=(2,0,2);set_positions(r,restored);r.save();r.request(3)
 assert bytes(r.files[one])!=before
 # Stale target/player still cannot save rearrangements into the home file.
 assert r.edit(0)==1;saved={k:bytes(v) for k,v in r.files.items()}
 r.put(M+0xf4,0x71000002);r.save();assert {k:bytes(v) for k,v in r.files.items()}==saved
 r.put(M+0xf4,0x71000001);r.put(PM+0x74,43);r.save()
 assert {k:bytes(v) for k,v in r.files.items()}==saved
 report=dict(full_original_neutral_roster_preserved=True,native_shop_kind_two_drag_mode_kept=True,
 type_and_quantity_changes_rejected=True,overlapping_cells_rejected=True,
 position_rearrangement_save_discard_restart=True,two_shops_and_home_isolated=True,
 failed_write_keeps_prior_layout_and_editor=True,legacy_v81_empty_save_repaired_without_open_write=True,
 corrupt_or_foreign_target_save_guarded=True,no_currency_army_or_ownership_change=True,
 actual_drag_and_hidden_controls_require_runtime_acceptance=True,runtime_game_verified=False)
 (OUT/'v82-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
