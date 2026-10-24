/* Own-profile signup links. Account contact codes keep their existing meaning. */
async function mountSignupInvite(host) {
 if (!host || typeof account === 'undefined' || !account?.id) return null;
 const owner = account.id;
 const existing = host.querySelector('[data-signup-invite]');
 if (existing?._inviteOwner === owner) return existing;
 existing?.remove();

 const make = (tag, text = '') => {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
 };
 const section = make('section');
 section.dataset.signupInvite = '1';
 section._inviteOwner = owner;
 section.className = 'profile-tab-section';
 const summary = make('div');
 summary.className = 'profile-list-row';
 summary.style.display = 'flex';
 summary.style.alignItems = 'center';
 summary.style.gap = '12px';
 const description = make('p', 'Your invite link lets someone sign up for X ORBIT.');
 description.style.flex = '1';
 const get = make('button', 'Get invite link');
 get.type = 'button';
 get.title = 'Show your personal X ORBIT sign-up link';
 summary.append(description, get);
 const details = make('div');
 details.hidden = true;
 const label = make('label', 'Your sign-up invite link');
 const field = make('input');
 field.type = 'url';
 field.readOnly = true;
 field.setAttribute('aria-label', 'Your sign-up invite link');
 label.append(field);
 const actions = make('div');
 actions.className = 'actions';
 actions.style.display = 'flex';
 actions.style.gap = '8px';
 actions.style.flexWrap = 'wrap';
 const copy = make('button', 'Copy link');
 const share = make('button', 'Share link');
 const reset = make('button', 'Reset link');
 for (const button of [get, copy, share, reset]) {
  button.type = 'button';
  button.style.padding = '8px 12px';
 }
 copy.title = 'Copy this sign-up link';
 share.title = 'Share this sign-up link with another person';
 reset.title = 'Create a replacement link and stop previous links from working';
 actions.append(copy, share, reset);
 details.append(label, actions);
 const status = make('p');
 status.className = 'muted';
 status.setAttribute('role', 'status');
 section.append(summary, details, status);
 host.append(section);

 let busy = false;
 let address = '';
 const connected = () => host.isConnected && section.isConnected && account?.id === owner;
 const setBusy = value => {
  busy = value;
  for (const button of [get, copy, share, reset]) button.disabled = value;
 };
 function inviteURL(result) {
  if (typeof result?.path !== 'string') throw Error('The server returned an invalid invite link. Try again.');
  const url = new URL(result.path, location.origin);
  if (url.origin !== location.origin || url.pathname !== '/join' || url.username || url.password || url.hash || !(url.searchParams.get('invite') || '').trim()) {
   throw Error('The server returned an invalid invite link. Try again.');
  }
  return url.href;
 }
 async function prepare(replace = false) {
  if (busy || !connected()) return;
  if (replace && !confirm('Reset your invite link? Previous links will stop working. Existing accounts and chats will stay unchanged.')) return;
  setBusy(true);
  status.textContent = replace ? 'Resetting your invite link…' : 'Preparing your invite link…';
  try {
   const result = await api(replace ? '/invitations/reset' : '/invitations/mine', replace ? {} : undefined);
   if (!connected()) return;
   const next = inviteURL(result);
   address = next;
   field.value = next;
   details.hidden = false;
   get.hidden = true;
   const joined = Number.isInteger(result.joined) && result.joined >= 0 ? result.joined : null;
   status.textContent = (replace ? 'New link ready. Previous links no longer work.' : 'Invite link ready.') + (joined === null ? '' : ' ' + joined + (joined === 1 ? ' person has' : ' people have') + ' joined through your invites.');
  } catch (error) {
   if (!connected()) return;
   status.textContent = error.message || 'The invite link could not be loaded. Try again.';
   if (!address) get.textContent = 'Retry';
  } finally {
   setBusy(false);
  }
 }
 function nativeBridge(method) {
  for (const bridge of [typeof GuardianGaming !== 'undefined' ? GuardianGaming : null, typeof GuardianSocial !== 'undefined' ? GuardianSocial : null]) {
   if (bridge && typeof bridge[method] === 'function') return value => bridge[method](value);
  }
  return null;
 }
 async function copyAddress() {
  const bridge = nativeBridge('copyInvite');
  if (bridge) await bridge(address);
  else if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(address);
  else {
   field.focus();
   field.select();
   throw Error('Select and copy the invite link above. Clipboard access is unavailable.');
  }
 }
 async function useLink(kind) {
  if (busy || !address || !connected()) return;
  setBusy(true);
  try {
   if (kind === 'copy') {
    await copyAddress();
    if (connected()) status.textContent = 'Invite link copied.';
   } else {
    const bridge = nativeBridge('shareInvite');
    if (bridge) await bridge(address);
    else if (navigator.share) await navigator.share({title: 'Join X ORBIT', text: 'Join me on X ORBIT.', url: address});
    else {
     await copyAddress();
     if (connected()) status.textContent = 'Invite link copied. Paste it into the app you want to share it in.';
     return;
    }
    if (connected()) status.textContent = 'Invite link is ready to share.';
   }
  } catch (error) {
   if (connected() && error.name !== 'AbortError') status.textContent = error.message || 'The invite link could not be shared. Try again.';
  } finally {
   setBusy(false);
  }
 }
 get.onclick = () => prepare();
 copy.onclick = () => useLink('copy');
 share.onclick = () => useLink('share');
 reset.onclick = () => prepare(true);
 return section;
}
