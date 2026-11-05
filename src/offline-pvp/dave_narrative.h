// The original narrative player, speaker and localized pages are retained.
// Only its old network acknowledgement is replaced for a local result.
static U daveNarrativeUser,daveNarrativeSerial;
static P daveNarrativeMap;
extern "C" U offlineDaveNarrative(U b,P map){
 if(!regular(b)||!ensureEconomy(b,manager(b)))return 0;
 P m=manager(b);const Economy&s=economyRuntime.state;
 // The original result dispatcher reads +160 and can otherwise repeat stale
 // server outcomes. The first-entry introduction has its own profile flag.
 at<I>(m,0x160)=-1;at<U>(m,0x158)=6;
 if(s.daveDialogueSerial==s.daveDialogueSeen)return 0;
 if(daveNarrativeUser==owner(b)&&daveNarrativeSerial==s.daveDialogueSerial&&daveNarrativeMap==map)return 1;
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);P player=at<P>(app,0x1358);if(!player)return 0;
 char key[64]{};const char*src=s.daveDialogueOutcome?"MAP_PVPEVILDAVID_SUCCESS_":"MAP_PVPEVILDAVID_FAILED_INTRO";U n=0;
 while(src[n]){key[n]=src[n];++n;}
 if(s.daveDialogueOutcome){key[n++]=char('0'+s.daveDialogueOutcome);const char*suffix="_INTRO";while(*suffix)key[n++]=*suffix++;}
 P name=nullptr,empty=nullptr;narrow(b,reinterpret_cast<P>(&name),key);narrow(b,reinterpret_cast<P>(&empty),"");
 // Match the native six-word function object: vtable, method, offset,
 // receiver, active flag, invoker. These functions are all native addresses.
 U callback[6]={b+0x1787408,b+(s.daveDialogueOutcome?0x10090c4:0x100906c),0,reinterpret_cast<U>(map),1,b+0x1008e90};
 daveNarrativeUser=owner(b);daveNarrativeSerial=s.daveDialogueSerial;daveNarrativeMap=map;
 call<void>(b,0x2af780,player,&name,callback,&empty);release(b,empty);release(b,name);
 log(b,"dave-dialogue-started",s.daveDialogueSerial,s.daveDialogueOutcome);return 1;
}
extern "C" U offlineDaveNarrativeAck(U b,P map){
 if(daveNarrativeMap!=map||!daveNarrativeSerial)return 0;
 if(!regular(b)||daveNarrativeUser!=owner(b)||!ensureEconomy(b,manager(b)))return 1;
 Economy next=economyRuntime.state;
 // A second invocation of the same callback is consumed locally too. A
 // cross-profile callback never acknowledges that player's pending message.
 if(daveNarrativeSerial!=next.daveDialogueSerial)return 1;
 if(next.daveDialogueSeen==next.daveDialogueSerial)return 1;
 next.daveDialogueSeen=next.daveDialogueSerial;
 if(commitProgression(b,manager(b),next))log(b,"dave-dialogue-confirmed",next.daveDialogueSeen,next.daveDialogueOutcome);
 return 1;
}
