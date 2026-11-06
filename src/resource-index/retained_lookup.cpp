// RSG file dictionaries are immutable for the lifetime of a loaded APK.
// Native consumers borrow the returned entry only to read its type/offset/size.
// Keep their small dictionary independently of the unloadable resource pools.
using U=unsigned;
using P=unsigned char*;
template<class R,class...A>static R call(U base,U offset,A...args){return reinterpret_cast<R(*)(A...)>(base+offset)(args...);}
struct Index {
 Index* next;
 U record,group,nameHash,words;
 U data[1];
};
static Index* buckets[64];
static U lockWord,usedBytes;
struct MapFile {
 MapFile* next;
 U hash,size,nameSize;
 unsigned char storage[1];
};
static MapFile* mapFiles[64];
static U mapBytes;
static U nameHash(const char* s){U h=2166136261u;for(U i=0;s&&i<1024&&s[i];++i)h=(h^static_cast<unsigned char>(s[i]))*16777619u;return h;}

extern "C" U* retainedResourceLookup(U base,P dictionary,const char* path){
 if(!dictionary)return nullptr;
 U words=*reinterpret_cast<U*>(dictionary+4);
 if(!words||words>0x100000)return call<U*>(base,0x1405fd0,dictionary,path);
 P record=dictionary-8;
 U group=*reinterpret_cast<U*>(record+20),hash=nameHash(*reinterpret_cast<const char**>(record));
 U bucket=((reinterpret_cast<U>(record)>>7)^hash)&63;
 call<int>(base,0x1479d4,&lockWord);
 Index* saved=buckets[bucket];
 while(saved&&(saved->record!=reinterpret_cast<U>(record)||saved->group!=group||saved->nameHash!=hash||saved->words!=words))saved=saved->next;
 if(!saved){
  U bytes=sizeof(Index)-sizeof(U)+words*sizeof(U);
  const U* source=*reinterpret_cast<const U**>(dictionary);
  if(source&&bytes<=16*1024*1024-usedBytes){
   saved=call<Index*>(base,0x147938,bytes);
   if(saved){
    saved->record=reinterpret_cast<U>(record);saved->group=group;saved->nameHash=hash;saved->words=words;
    for(U i=0;i<words;++i)saved->data[i]=source[i];
    saved->next=buckets[bucket];buckets[bucket]=saved;usedBytes+=bytes;
   }
  }
 }
 call<int>(base,0x1479e0,&lockWord);
 if(!saved)return call<U*>(base,0x1405fd0,dictionary,path);
 U owned[2]={reinterpret_cast<U>(saved->data),saved->words};
 return call<U*>(base,0x1405fd0,owned,path);
}

static unsigned char folded(unsigned char c){return c=='/'?'\\':(c>='a'&&c<='z'?c-32:c);}
static bool mapAnimation(const char* path,U& length,U& hash){
 if(!path)return false;
 length=0;hash=2166136261u;bool world=false;
 const char part[]="\\WORLDMAP\\";
 for(;length<1024&&path[length];++length){
  unsigned char c=folded(path[length]);hash=(hash^c)*16777619u;
  if(c=='\\'){
   U j=0;while(part[j]&&path[length+j]&&folded(path[length+j])==static_cast<unsigned char>(part[j]))++j;
   if(!part[j])world=true;
  }
 }
 return world&&length<1024&&length>=4&&path[length-4]=='.'&&folded(path[length-3])=='P'&&folded(path[length-2])=='A'&&folded(path[length-1])=='M';
}
static bool sameName(const MapFile* file,const char* path,U length){
 if(file->nameSize!=length)return false;
 for(U i=0;i<length;++i)if(file->storage[i]!=folded(path[i]))return false;
 return true;
}
extern "C" void retainedMapBuffer(U base,P buffer,const char* path,const unsigned char* source,U size){
 U length=0,hash=0;
 if(!size||size>8*1024*1024||!mapAnimation(path,length,hash)){call<void>(base,0x112d864,buffer,source,size);return;}
 U bucket=hash&63;
 call<int>(base,0x1479d4,&lockWord);
 MapFile* saved=mapFiles[bucket];
 while(saved&&(saved->hash!=hash||saved->size!=size||!sameName(saved,path,length)))saved=saved->next;
 if(!saved){
  U bytes=sizeof(MapFile)-1+length+1+size;
  if(source&&bytes<=64*1024*1024-mapBytes){
   saved=call<MapFile*>(base,0x147938,bytes);
   if(saved){
    saved->hash=hash;saved->size=size;saved->nameSize=length;
    for(U i=0;i<length;++i)saved->storage[i]=folded(path[i]);
    saved->storage[length]=0;
    for(U i=0;i<size;++i)saved->storage[length+1+i]=source[i];
    saved->next=mapFiles[bucket];mapFiles[bucket]=saved;mapBytes+=bytes;
   }
  }
 }
 call<int>(base,0x1479e0,&lockWord);
 call<void>(base,0x112d864,buffer,saved?saved->storage+saved->nameSize+1:source,size);
}
