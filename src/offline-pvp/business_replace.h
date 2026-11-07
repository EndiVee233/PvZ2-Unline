// Shop keepers are independent of residential encounters. Reuse the saved
// occupier fields, retaining the shop's garrison and any uncollected stock.
extern "C" U offlineBusinessReplaceMode(){return 1;}
static U replaceBusinessOpponent(U b,P panel){
 if(panel!=businessReplacePanel||businessReplaceUser!=owner(b)||at<U>(panel,0xa4)!=3)return 1;
 const BusinessPlot*s=businessPlot(at<U>(panel,0xac),at<U>(panel,0xa8));
 P m=manager(b),map=at<P>(panel,0xc0);
 if(!s||!map||!ensureEconomy(b,m)||!regionOpen(s->zone))return 1;
 const Economy&old=economyRuntime.state;U bit=businessBit(s->id),index=bit==1?0:1;
 if(old.businessOwnedMask&bit||old.battleOpen)return 1;
 Economy next=old;
 U rng=neighborMix(old.user^old.sequence^s->id^old.shopEnemySeed[index]^0x491ec573u);
 U id=0;for(U i=0;i<NPC_COUNT;++i)if(!NPCS[i].evil&&regionOpen(NPCS[i].zone)&&NPCS[i].id!=old.shopEnemy[index]){id=NPCS[i].id;break;}
 if(!id)return 1;
 U previous[40]{},title[40]{};
 if(old.shopEnemy[index])neighborName(old.shopEnemySeed[index],old.shopEnemyKind[index],previous);
 else for(U i=0;i<8;++i)previous[i]=s->name[i];
 bool different=false;U seed=0;
 for(U attempt=0;attempt<64&&!different;++attempt){
  seed=neighborRandom(rng);neighborName(seed,0,title);
  for(U i=0;i<40;++i){if(previous[i]!=title[i]){different=true;break;}if(!title[i])break;}
 }
 if(!different)return 1;
 next.shopEnemy[index]=id;next.shopEnemySeed[index]=seed;next.shopEnemyKind[index]=0;
 ++next.sequence;
 if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 economyRuntime.state=next;projectBusinessOwners(b,m);
 log(b,"business-opponent-replaced",s->id,seed);
 U zone=s->zone,pos=s->position;businessReplacePanel=nullptr;
 call<void>(b,0x100a864,map);call<void>(b,0x1019668,map,3,zone,pos);
 return 1;
}
