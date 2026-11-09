// The stage loader (0x204b00) records the horizontal artwork bounds in board
// coordinates. libczProject adjusts the board and graphics translation again
// just before drawing, after the intro timeline has finished moving the board.
extern "C" void boardCameraDraw(U base,P board,P graphics){
 constexpr U drawBoard=0x235048;
 P holder=at<P>(reinterpret_cast<P>(base),0x1821674);
 P app=holder?at<P>(holder,0):nullptr;
 I width=app?at<I>(app,0x524):0;
 I left=at<I>(board,0x994);
 I right=at<I>(board,0x34);
 if(!at<P>(board,0x938)||width<=0||left>0||right<=0){
  call<void>(base,drawBoard,board,graphics);
  return;
 }

 I minimum=width-right;
 I maximum=-left;
 I x=at<I>(board,0x2c);
 I bounded=x<minimum?minimum:x>maximum?maximum:x;
 bool widerThanStage=minimum>maximum;
 if(widerThanStage)bounded=maximum+(minimum-maximum)/2;
 at<I>(board,0x2c)=bounded;
 at<float>(graphics,8)+=static_cast<float>(bounded-x);

 // On an ultrawide window, center the stage and clip the world to its artwork.
 // The original screen clip is restored for the HUD.
 I clipX=at<I>(graphics,0x20);
 I clipWidth=at<I>(graphics,0x28);
 if(widerThanStage){
  I translated=static_cast<I>(at<float>(graphics,8));
  I artworkLeft=translated+left;
  I artworkRight=translated+right;
  I start=artworkLeft>clipX?artworkLeft:clipX;
  I end=artworkRight<clipX+clipWidth?artworkRight:clipX+clipWidth;
  at<I>(graphics,0x20)=start;
  at<I>(graphics,0x28)=end>start?end-start:0;
 }
 call<void>(base,drawBoard,board,graphics);
 if(widerThanStage){
  at<I>(graphics,0x20)=clipX;
  at<I>(graphics,0x28)=clipWidth;
 }
}
