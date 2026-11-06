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
