'use strict';
// Extend the existing destinations; chat/call actions and account state stay intact.
const originalChooseHome=chooseHome;
const mainNavigation=document.querySelector('.orbit-bottom-nav');
function syncMainNavigation(){
 mainNavigation.hidden=!account||!['contacts','profile'].includes(activeScreen);
 const selected=activeScreen==='profile'?'profile':homeMode==='calls'?'calls':'chats';
 for(const key of ['vibe','chats','calls','profile']){const b=el(key+'Tab'),on=key===selected;b.setAttribute('aria-selected',String(on));b.setAttribute('aria-pressed',String(on));b.tabIndex=on?0:-1}
}
chooseHome=mode=>{if(activeScreen!=='contacts')contacts();originalChooseHome(mode);syncMainNavigation()};
el('vibeTab').onclick=()=>location.assign('/vibe.html');
el('profileTab').onclick=async()=>{await showProfile(account.id);syncMainNavigation()};
for(const mode of ['chats','calls'])el(mode+'Tab').onclick=()=>chooseHome(mode);
mainNavigation.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const items=[...mainNavigation.querySelectorAll('button')],index=items.indexOf(document.activeElement),next=e.key==='Home'?0:e.key==='End'?3:(index+(e.key==='ArrowRight'?1:3))%4;items[next].focus();items[next].click()};
const originalShow=show;show=which=>{originalShow(which);syncMainNavigation()};
const management=document.createElement('div');management.className='profile-management';
for(const [label,fn] of [['Settings',()=>toggleSettings(true)],['Personalization',()=>{toggleSettings(true);document.getElementById('openPersonalization')?.click()}]]){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=fn;management.append(b)}
el('profile').append(management);const oldProfile=showProfile;showProfile=async id=>{await oldProfile(id);management.hidden=id!==account?.id;syncMainNavigation()};
syncMainNavigation();
