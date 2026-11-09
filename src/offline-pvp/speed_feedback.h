static U pendingSpeedFeedback;

extern "C" U offlineSpeedFeedbackRate(U b){
 P app=pvpMusicApp(b);
 P board=app?at<P>(app,0x6bc):nullptr;
 if(!board||at<U>(board,0xc0)!=5||at<unsigned char>(board,0x8d5))return 0;
 P controller=at<P>(reinterpret_cast<P>(b),0x1830528);
 return controller?at<U>(controller,0x30):0;
}

extern "C" void offlineSpeedFeedbackChanged(U b,U before){
 constexpr U normal=0x3f800000,fast=0x40000000;
 if(before!=normal&&before!=fast)return;
 U after=offlineSpeedFeedbackRate(b);
 if(after!=normal&&after!=fast)return;
 if(before==after)return;
 pendingSpeedFeedback=after==fast?2:1;
 log(b,"speed-feedback",pendingSpeedFeedback,0);
}
