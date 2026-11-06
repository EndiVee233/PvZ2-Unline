// A shop owns a fixed set of plants. Its native kind-2 editor moves those
// plants and deliberately has no seed bank or shovel. Guard the serialized
// roster as well, independently of UI visibility and keyboard routing.
static U garrisonRosterSize,garrisonPlantCount;
static U garrisonRosterTypes[128],garrisonRosterCounts[128];
static void bindGarrisonRoster(const Store&s){
 garrisonRosterSize=0;garrisonPlantCount=s.positions;
 for(U k=0;k<s.positions;++k){U i=0;while(i<garrisonRosterSize&&garrisonRosterTypes[i]!=s.pos[k].type)++i;
  if(i==garrisonRosterSize){garrisonRosterTypes[i]=s.pos[k].type;garrisonRosterCounts[i]=0;++garrisonRosterSize;}
  ++garrisonRosterCounts[i];
 }
}
static bool validGarrisonMove(const Store&s){
 if(!garrisonRosterSize||s.positions!=garrisonPlantCount)return false;
 for(U k=0;k<s.positions;++k){bool known=false;
  for(U i=0;i<garrisonRosterSize;++i)if(s.pos[k].type==garrisonRosterTypes[i])known=true;
  if(!known)return false;
  for(U j=0;j<k;++j)if(s.pos[k].row==s.pos[j].row&&s.pos[k].col==s.pos[j].col)return false;
 }
 for(U i=0;i<garrisonRosterSize;++i){U n=0;
  for(U k=0;k<s.positions;++k)if(s.pos[k].type==garrisonRosterTypes[i])++n;
  if(n!=garrisonRosterCounts[i])return false;
 }
 return true;
}
