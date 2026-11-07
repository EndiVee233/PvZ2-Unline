// Reuse the original compensation/new-player code dialogs on the game thread.
// No SDK callback, network reply, or per-account 'used code' flag is involved.
extern "C" U offlineRedeem(U b,P ui){
 if(!ui)return 0;
 P input=at<P>(ui,0xac);if(!input)return 0;
 P code=at<P>(input,0xa4);if(!code||at<U>(code-12,0)!=5)return 0;
 const U*text=reinterpret_cast<const U*>(code);
#ifdef PVP_SILENT_RAID_TEST
 if(text[0]=='r'&&text[1]=='a'&&text[2]=='i'&&text[3]=='d'&&text[4]=='!'&&!text[5]){
  P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);call<void>(b,0x3feb40,app);silentTestArm(b);return 1;
 }
#endif
 if(text[0]!='a'||text[1]!='d'||text[2]!='m'||text[3]!='i'||text[4]!='n'||text[5])return 0;
 // The confirm button opens App+0x1344 before invoking the submit method.
 // Match the real OnRequestFinished cleanup even though no request is sent.
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);
 call<void>(b,0x3feb40,app);
 P p=profile(b);if(!p)return 1;
 // Reject both awards together at the native signed currency limit.
 U coinKey=at<U>(p,0x9c),gemKey=at<U>(p,0xa4);
 U coinShift=coinKey&31,gemShift=gemKey&31;
 U coin=at<U>(p,0x98),gem=at<U>(p,0xa0);
 coin=((coin>>coinShift)|(coin<<((32-coinShift)&31)))^coinKey;
 gem=((gem>>gemShift)|(gem<<((32-gemShift)&31)))^gemKey;
 if(coin>2147483647u-10000||gem>2147483647u-100){economyNotice(b,"[V39_ADMIN_LIMIT]");return 1;}
 call<void>(b,0x745220,p,100,1);
 call<void>(b,0x746164,p,10000);
 // These native award methods refresh the currency bars, mark the profile
 // dirty and run its normal persistence notification; never edit save bytes.
 log(b,"admin-redeemed",100,10000);
 economyNotice(b,"[V39_ADMIN_GRANTED]");return 1;
}

extern "C" P offlineCodeCard(U b,P card,U id,P listener){
 call<void>(b,0x7f90fc,card,id,listener);
 // The old lost-items picture is optional in the original card renderer.
 if(id==2000)at<P>(card,0xec)=nullptr;
 return card;
}
