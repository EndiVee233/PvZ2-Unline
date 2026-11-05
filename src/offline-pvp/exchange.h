// The native shop already chooses and persists its six goods. A purchase's
// medal debit and delivery journal share the atomic per-player wallet file.
// The journal retains the last delivery until replaced by the next purchase.
// Native inventory and the native purchased-ID list are flushed together,
// letting a restart replay an interrupted debit without delivering twice.
static bool exchangeBusy;
static bool exchangeBought(U b,U id){
 P p=profile(b),first=at<P>(p,0x7a8),end=at<P>(p,0x7ac);
 if(end<first||U(end-first)>4096||U(end-first)%4)return false;
 for(P q=first;q<end;q+=4)if(at<U>(q,0)==id)return true;
 return false;
}
static bool recoverExchange(U b,P shop){
 const Economy&s=economyRuntime.state;
 if(!s.shopItem||exchangeBought(b,s.shopItem))return true;
 P current=profile(b);
 // A native day rollover clears its bought-ID vector. That is a new stock
 // generation, not evidence that an old purchase still needs delivery.
 if(at<U>(current,0x798)!=s.shopDay||at<U>(current,0x794)!=s.shopRefresh)return true;
 if(exchangeBusy)return false;
 const ExchangeSpec*spec=exchangeSpec(s.shopItem);
 if(!spec||spec->quantity!=s.shopQuantity||spec->price!=s.shopPrice)return false;
 exchangeBusy=true;
 P p=profile(b),pm=call<P>(b,0x1df738);
 unsigned char held=at<unsigned char>(pm,0x81);
 at<unsigned char>(pm,0x81)=1;
 // All native grant methods call MarkDirty. Hold its file writer until the
 // item and purchased-ID flag are both present in that same native profile.
 call<void>(b,0x71e15c,p,s.shopItem);
 call<void>(b,0x106c884,shop,s.shopItem,s.shopQuantity);
 at<unsigned char>(pm,0x81)=held;
 call<void>(b,0x7110c4,p);
 exchangeBusy=false;
 bool ok=exchangeBought(b,s.shopItem);
 log(b,ok?"exchange-delivered":"exchange-delivery-pending",s.shopItem,s.shopQuantity);
 return ok;
}
extern "C" U offlineExchangePrepare(U b,P shop,U refresh){
 if(!regular(b))return 0;
 if(shop!=manager(b)+0x200)return 1;
 if(!ensureEconomy(b,manager(b))||!recoverExchange(b,shop))return 1;
 if(refresh){economyNotice(b,"[V71_EXCHANGE_REFRESH_PENDING]");return 1;}
 return 0; // Preserve original local catalogue generation and layout.
}
extern "C" U offlineExchangeBuy(U b,P shop,U id){
 if(!regular(b))return 0;
 P m=manager(b);
 if(shop!=m+0x200||exchangeBusy||!ensureEconomy(b,m))return 1;
 if(!recoverExchange(b,shop))return 1;
 const ExchangeSpec*spec=exchangeSpec(id);
 P first=at<P>(shop,0x4c),end=at<P>(shop,0x50),offer=nullptr;
 if(end<first||U(end-first)>16*6||U(end-first)%16)return 1;
 for(P q=first;q<end;q+=16)if(at<U>(q,0)==id){offer=q;break;}
 if(!spec||!offer||at<U>(offer,4)!=spec->quantity||at<U>(offer,8)!=spec->price||at<U>(offer,12)||exchangeBought(b,id))return 1;
 tickProgression(b);
 Economy next=economyRuntime.state;
 if(next.medals<spec->price){economyNotice(b,"[V71_EXCHANGE_MEDALS_REQUIRED]");return 1;}
 next.medals-=spec->price;next.shopItem=id;next.shopQuantity=spec->quantity;next.shopPrice=spec->price;
 next.shopDay=at<U>(profile(b),0x798);next.shopRefresh=at<U>(profile(b),0x794);
 if(!commitProgression(b,m,next))return 1;
 log(b,"exchange-debited",id,spec->price);
 recoverExchange(b,shop);
 return 1;
}
