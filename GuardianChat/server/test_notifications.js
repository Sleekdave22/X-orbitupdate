const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/index.html','utf8');
const line=name=>source.split('\n').find(l=>l.startsWith('function '+name+'(')||l.startsWith('async function '+name+'('));
let sounds=0,resets=0,users=[];const banner={textContent:'',hidden:true};
const ctx={activeScreen:'chat',peer:{id:'s21'},account:{id:'me'},document:{hidden:false},window:{},localStorage:{getItem:()=>null,setItem:()=>{}},applyChatPresentation:()=>{},alertsPrimed:true,alertLatest:{s21:100},el:()=>banner,clearInlineMedia:()=>{resets++},playMessageSound:()=>{sounds++},setTimeout:()=>{},api:async path=>path==='/inbox'?{ids:[]}:path==='/gamebox/summary'?{config:{},notices:[]}:{users}};
vm.createContext(ctx);vm.runInContext(line('openChat')+'\n'+line('alerts'),ctx);
(async()=>{ctx.openChat({id:'s21',name:'S21'});assert.equal(resets,0,'Selecting the open chat must not reload it');ctx.activeScreen='contacts';
for(const latest of [90,100]){users=[{id:'s21',latest,unread:1,name:'S21'}];await ctx.alerts();assert.equal(sounds,0,'Older snapshots must not replay notifications');assert.equal(ctx.alertLatest.s21,100)}
users=[{id:'s21',latest:101,unread:1,name:'S21'}];await ctx.alerts();assert.equal(sounds,1,'A genuinely new message still alerts');await ctx.alerts();assert.equal(sounds,1,'The same message must not alert twice');
ctx.activeScreen='chat';users=[{id:'s21',latest:102,unread:1,name:'S21'}];await ctx.alerts();assert.equal(sounds,1,'Visible chat must not receive a background alert');console.log('Notification regression checks passed');})().catch(e=>{console.error(e);process.exitCode=1});
