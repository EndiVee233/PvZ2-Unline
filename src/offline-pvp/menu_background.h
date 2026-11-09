#ifdef MENU_BACKGROUND_COVER
struct MenuRect { I x,y,width,height; };

extern "C" void drawWideMenuBackground(U base,P graphics,P image,I x,I y,I width,I height){
 if(!image||width<=0||height<=0)return;
 I imageWidth=at<I>(image,0x28);
 I imageHeight=at<I>(image,0x2c);
 if(imageWidth<=0||imageHeight<=0)return;
 constexpr U divide=0x15ddedc; // __aeabi_idiv
 MenuRect source{0,0,imageWidth,imageHeight};
 const MenuRect viewport{x,y,width,height};
 if(width*imageHeight>height*imageWidth){
  source.height=call<I>(base,divide,imageWidth*height,width);
  if(source.height<1)source.height=1;
  source.y=(imageHeight-source.height)/2;
  // Keep the logo near the upper third in very wide windows.
  const I maxTop=imageHeight/6;
  if(source.y>maxTop)source.y=maxTop;
 }else{
  source.width=call<I>(base,divide,imageHeight*width,height);
  if(source.width<1)source.width=1;
  source.x=(imageWidth-source.width)/2;
 }
 call<void>(base,0x11699c4,graphics,image,&viewport,&source);
}
#else
struct MenuColor { I red,green,blue,alpha; };

extern "C" void drawWideMenuBackground(U base,P graphics,P image,I x,I y,I width,I height){
 constexpr U drawScaled=0x11698b4,setColor=0x1166c30,fillRect=0x1167010;
 if(!image)return;
 I sourceWidth=at<I>(image,0x28);
 I sourceHeight=at<I>(image,0x2c);
 if(width>0&&height>0&&sourceWidth>0&&sourceHeight>0){
  I fittedWidth=call<I>(base,0x15ddedc,height*sourceWidth,sourceHeight); // __aeabi_idiv
  if(fittedWidth>0&&fittedWidth<width){
   // Keep the full artwork, then let the original menu draw its controls
   // using the full viewport. Restore the graphics tint before drawing.
   I left=(width-fittedWidth)/2;
   I right=width-fittedWidth-left;
   MenuColor previous=at<MenuColor>(graphics,0x4c);
   MenuColor black{0,0,0,255};
   call<void>(base,setColor,graphics,&black);
   if(left)call<void>(base,fillRect,graphics,x,y,left,height);
   call<void>(base,fillRect,graphics,x+left+fittedWidth,y,right,height);
   call<void>(base,setColor,graphics,&previous);
   x+=left;
   width=fittedWidth;
  }
 }
 call<void>(base,drawScaled,graphics,image,x,y,width,height);
}
#endif
