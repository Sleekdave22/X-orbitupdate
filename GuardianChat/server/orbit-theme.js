const OrbitTheme=Object.freeze({
 tokens:{accent:'#7C3AED',secondary:'#22D3EE',paper:'#0B1520',ink:'#F1F5F9',lightAction:'#0E7490',surface:'#131932'},
 color(value){return value},
 brand(value){return ['GuardianChat','Guardian Chat','X ORBIT','ORBIT'].includes(value)?'X ORBIT':value},
 chat(value){return ['GuardianChat','Guardian Chat','X ORBIT','ORBIT','Orbit Chat','OrbitChat'].includes(value)?'OrbitChat':value},
 gaming(value){return ['Gamebox','GameBox','Clutch Naija'].includes(value)?'OrbitPlay':value}
});
