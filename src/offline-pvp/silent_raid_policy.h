// User-designed offline odds. One basis point is 1/10000. Five tier-one
// plants are the reference line (the original first-defense tutorial).
struct RaidOdds {U attack,win;}; // win is a joint probability, not conditional.
static U raidDivide(U value,U divisor){
 U quotient=0,remainder=0;
 for(U bit=32;bit;--bit){remainder=(remainder<<1)|((value>>(bit-1))&1);if(remainder>=divisor){remainder-=divisor;quotient|=1u<<(bit-1);}}
 return quotient;
}
static U defenseStrength(const Store&s){
 U strength=0;
 for(U i=0;i<s.positions;++i){U tier=1;
  for(U k=0;k<s.infos;++k)if(s.info[k].type==s.pos[i].type){tier=s.info[k].level;break;}
  if(!tier)tier=1;if(tier>5)tier=5;
  strength+=1+2*(tier-1);
 }
 return strength;
}
static RaidOdds defenseOdds(U strength){
 // Reference: total 10%, attacker win 5%, attacker loss 5%.
 // Increasing plant count or tier lowers both attack frequency and the
 // attacker's conditional win chance. Empty lines are more vulnerable.
 if(strength>1152)strength=1152;
 U divisor=5+strength,attack=raidDivide(10000,divisor),conditional=raidDivide(50000,divisor);
 if(conditional>10000)conditional=10000;
 return {attack,attack*conditional/10000};
}
static U raidLoss(U amount){return amount/20;}
