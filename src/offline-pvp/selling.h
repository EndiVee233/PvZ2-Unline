// Original camp sale controls: vector +e4, card name +a8, available +ac,
// selected-for-sale +b0. The native quote is count * (training cost >> 1).
static P sellingUi,sellingVtable;
static U sellingUser;
extern "C" void offlineSellReady(U b,P ui){
 if(!regular(b)||!ui)return;
 sellingUi=ui;sellingVtable=at<P>(ui,0);sellingUser=owner(b);
}
static void clearSaleSelection(U b,P ui,P begin,P end){
 for(P p=begin;p<end;p+=4){P card=at<P>(p,0);if(card)call<void>(b,0x1052168,card,0);}
 call<void>(b,0x1056f84,ui,0);
}
extern "C" U offlineSellConfirm(U b,P ui,U confirmed){
 if(!regular(b))return 0;
 if(!ui||sellingUi!=ui||sellingUser!=owner(b)||at<P>(ui,0)!=sellingVtable)return 1;
 P begin=at<P>(ui,0xe4),end=at<P>(ui,0xe8);
 if(!begin||end<begin||U(end-begin)>64*4||U(end-begin)%4)return 1;
 if(!confirmed){clearSaleSelection(b,ui,begin,end);return 1;}
 P m=manager(b);if(!ensureEconomy(b,m)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 settleTraining(b,m);tickProgression(b);
 EconomyRuntime&r=economyRuntime;
 if(r.state.battleOpen){economyNotice(b,"[V101_SALE_CHANGED]");return 1;}
 U wanted[TRAIN_COUNT]{},total=0,refund=0;
 for(P p=begin;p<end;p+=4){
  P card=at<P>(p,0);if(!card)continue;U count=at<U>(card,0xb0);if(!count)continue;
  P name=at<P>(card,0xa8);U index=TRAIN_COUNT;
  if(name)for(U i=0;i<TRAIN_COUNT;++i)if(same(reinterpret_cast<const char*>(name),TRAIN_SPECS[i].name)){index=i;break;}
  if(index==TRAIN_COUNT||count>r.state.trains[index].held||wanted[index]){economyNotice(b,"[V101_SALE_CHANGED]");return 1;}
  wanted[index]=count;total+=count;refund+=count*(TRAIN_SPECS[index].cost>>1);
 }
 if(!total){clearSaleSelection(b,ui,begin,end);return 1;}
 if(refund>2000000000u-r.state.coins){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 Economy next=r.state;next.coins+=refund;
 for(U i=0;i<TRAIN_COUNT;++i)next.trains[i].held-=wanted[i];
 ++next.sequence;
 if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 r.state=next;
 // These are display copies, not a second inventory. Refresh them before
 // leaving sale mode; the usual camp event refreshes capacity and other views.
 for(P p=begin;p<end;p+=4){P card=at<P>(p,0);if(!card)continue;P name=at<P>(card,0xa8);
  if(name)for(U i=0;i<TRAIN_COUNT;++i)if(same(reinterpret_cast<const char*>(name),TRAIN_SPECS[i].name)){at<U>(card,0xac)=next.trains[i].held;break;}
 }
 // Finish touching the old card vector before currency/camp notifications:
 // native listeners may rebuild those widgets synchronously.
 clearSaleSelection(b,ui,begin,end);applyEconomy(b,m);notifyTraining(b,m);log(b,"troops-sold",total,refund);return 1;
}
