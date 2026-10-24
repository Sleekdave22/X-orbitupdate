/* APK-only compatibility for comparing the X-orbit interface with the shared server.
 * No server data, rating policy, credentials or approved stylesheet is changed. */
(function () {
  'use strict';
  if (window.XOrbitComparison) return;
  const nativeFetch = window.fetch.bind(window);
  const explanation = 'Competition editing is available in X ORBIT Original while you compare interfaces.';
  const readCache = new Map();
  let cacheScope = null, installed = false;
  const forkTheme = Object.freeze({accent:'#7C3AED',surface:'#131932',paper:'#0B1520',ink:'#F1F5F9',radius:16,tab_padding:12,font_size:14,font_family:'system-ui'});
  const clone = value => JSON.parse(JSON.stringify(value));
  const headerText = document.querySelector('header h1')?.textContent || 'Orbit Play';
  const forkTabs = Array.from(document.querySelectorAll('nav [data-tab]'), item => item.dataset.tab).filter(key => !['admin','studio'].includes(key));
  const mutablePaths = /^\/(?:gaming|gamebox|identities|rankings|scheduling)(?:\/|$)/;

  function requestInfo(input, init) {
    const isRequest = typeof Request !== 'undefined' && input instanceof Request;
    const url = new URL(isRequest ? input.url : String(input), location.href);
    return {url, method:String(init?.method || (isRequest ? input.method : 'GET')).toUpperCase(), isRequest};
  }
  function optionsForReads(input, init, info) {
    const headers = init?.headers || (info.isRequest ? input.headers : undefined);
    return {method:'GET', headers, credentials:init?.credentials || (info.isRequest ? input.credentials : 'same-origin'), signal:init?.signal || (info.isRequest ? input.signal : undefined), cache:'no-store'};
  }
  function jsonResponse(value, source, status) {
    const headers = new Headers(source?.headers);
    headers.delete('content-length'); headers.delete('content-encoding');
    headers.set('Content-Type','application/json'); headers.set('Cache-Control','no-store');
    return new Response(JSON.stringify(value), {status:status || source?.status || 200, headers});
  }
  async function read(path, options) {
    const scope = new Headers(options.headers).get('Authorization') || '';
    if (scope !== cacheScope) {readCache.clear(); cacheScope = scope;}
    const previous = readCache.get(path);
    if (previous && previous.until > Date.now() && !options.signal?.aborted) return clone(await previous.value);
    const value = (async () => {
      const response = await nativeFetch(path, options);
      const body = await response.json();
      if (!response.ok) throw Error(body.error || 'Shared server information is unavailable');
      return body;
    })();
    const entry = {until:Date.now()+15000, value};
    readCache.set(path, entry);
    if (readCache.size > 64) readCache.delete(readCache.keys().next().value);
    try {return clone(await value);} catch (error) {if (readCache.get(path) === entry) readCache.delete(path); throw error;}
  }
  function presentation(config) {
    const result = {...config, theme:{...forkTheme}};
    // Retain this checkout's labels, tab order and CSS rather than publishing a theme.
    result.presentation = {...config?.presentation, game_tabs:forkTabs.slice(), custom_sections:[], labels:{...config?.presentation?.labels, gaming:headerText}};
    return result;
  }
  async function adaptEngine(source, options) {
    const body = clone(source);
    body.config = presentation(body.config || {});
    delete body.config.start_rating; // The fork's 1,000 default is not the shared policy.
    body.comparison = {read_only:true, explanation, rating_errors:[], ranking_policy:null};
    try {body.comparison.ranking_policy = await read('/rankings/policy', options);}
    catch (_) {body.comparison.rating_errors.push('The ranking policy could not be loaded.');}
    const games = Array.from(new Set([...(body.ratings || []), ...(body.ids || [])].map(item => item.game).filter(game => typeof game === 'string')));
    body.rating_cards = await Promise.all(games.map(async game => {
      const supplied = (body.ratings || []).find(item => item.game === game);
      let profile = supplied;
      if (!profile || typeof profile.provisional !== 'boolean') {
        try {profile = await read('/rankings/profile?game='+encodeURIComponent(game), options);}
        catch (_) {body.comparison.rating_errors.push('The '+game+' rating could not be loaded.'); return null;}
      }
      if (!Number.isFinite(profile.rating)) return null;
      let history = null, leaderboard = null;
      const extra = await Promise.allSettled([
        read('/rankings/history?game='+encodeURIComponent(game), options),
        read('/rankings/leaderboard?game='+encodeURIComponent(game)+'&mine=1&limit=1', options)
      ]);
      if (extra[0].status === 'fulfilled') history = extra[0].value.history;
      if (extra[1].status === 'fulfilled') leaderboard = extra[1].value;
      const card = {
        game, rating:profile.rating, tier:profile.grade || (profile.provisional ? 'Provisional' : 'Grade unavailable'),
        provisional:profile.provisional, matches:profile.verified_placements,
        rank:leaderboard?.my_rank?.global_rank ?? null, rank_available:!!leaderboard,
        wins:null, draws:null, losses:null, win_pct:null,
        history_available:Array.isArray(history), history:[],
        placement_required:profile.placement_required, policy:profile.policy
      };
      // Display only values returned by the authoritative history endpoint. Never
      // recalculate skill, synthesize an opponent rating or treat 25 rows as lifetime W/L.
      if (Array.isArray(history)) card.history = history.filter(item => Number.isFinite(item.rating_before) && Number.isFinite(item.rating_after)).map(item => ({
        before:item.rating_before, after:item.rating_after, change:item.rating_after-item.rating_before,
        outcome:item.outcome === 'W' ? 1 : item.outcome === 'D' ? 0.5 : item.outcome === 'L' ? 0 : null,
        created:item.created, kind:item.kind, source:item.source
      }));
      return card;
    }));
    body.rating_cards = body.rating_cards.filter(Boolean);
    return body;
  }
  async function adaptGaming(source, options) {
    const body = clone(source);
    if (body.profile && !body.profile.game_ids) {
      try {
        const own = await read('/identities/mine', options);
        body.profile.game_ids = Object.fromEntries((own.identities || []).filter(item => item.state === 'active').map(item => [item.game,item.game_id]));
      } catch (_) {body.profile.game_ids = {};}
    }
    return body;
  }
  function adaptStudio(source) {
    const body = clone(source);
    const supported = typeof STUDIO_FIELDS === 'undefined' ? [] : Object.keys(STUDIO_FIELDS);
    body.limits = Object.fromEntries(Object.entries(body.limits || {}).filter(([key]) => supported.includes(key)));
    for (const kind of ['published','draft']) if (body[kind]?.config) {
      try {
        const displayed = presentation(JSON.parse(body[kind].config));
        // The fork's editor has no label for its Ratings tab. Keep that tab in
        // navigation, but omit the unsupported editor row instead of "undefined".
        displayed.presentation.game_tabs = displayed.presentation.game_tabs.filter(tab => tab !== 'ratings');
        body[kind].config = JSON.stringify(displayed);
      }
      catch (_) { /* Preserve a server error rather than inventing a draft. */ }
    }
    return body;
  }
  window.fetch = async function (input, init) {
    let info;
    try {info = requestInfo(input, init);} catch (_) {return nativeFetch(input, init);}
    if (info.url.origin !== location.origin) return nativeFetch(input, init);
    const path = info.url.pathname;
    if (!['GET','HEAD','OPTIONS'].includes(info.method) && mutablePaths.test(path)) {
      return jsonResponse({error:explanation, comparison_read_only:true}, null, 409);
    }
    const response = await nativeFetch(input, init);
    if (info.method !== 'GET' || !response.ok || !['/gamebox/summary','/gaming/summary','/gamebox/studio'].includes(path)) return response;
    let value;
    try {value = await response.clone().json();} catch (_) {return response;}
    const options = optionsForReads(input, init, info);
    if (path === '/gamebox/summary') value = await adaptEngine(value, options);
    else if (path === '/gaming/summary') value = await adaptGaming(value, options);
    else value = adaptStudio(value);
    return jsonResponse(value, response);
  };
  function textNode(tag, value, cls) {
    const item = document.createElement(tag); item.textContent = value;
    if (cls) item.className = cls;
    return item;
  }
  function ratingDisplay() {
    if (typeof tab === 'undefined' || tab !== 'ratings' || typeof data === 'undefined' || !data?.engine) return;
    const view = document.getElementById('view'); if (!view) return;
    const engine = data.engine, cards = engine.rating_cards || [];
    view.replaceChildren();
    if (!cards.length) view.append(textNode('p','Ratings are supplied by the shared server. Add your game in X ORBIT Original to begin.','muted'));
    for (const c of cards) {
      const card = textNode('div','', 'card');
      card.append(textNode('h3',(data.games?.[c.game] || c.game)+' · '+c.tier),textNode('div',String(c.rating)+(c.provisional?' (provisional)':''),'score'));
      const rank = c.rank_available ? (c.rank ? '#'+c.rank : 'not yet ranked') : 'unavailable';
      card.append(textNode('p','Global rank '+rank+' · '+(Number.isFinite(c.matches)?c.matches:'—')+' verified matches','muted'));
      if (c.provisional && Number.isFinite(c.placement_required)) card.append(textNode('p','Placement matches required: '+c.placement_required,'muted'));
      const list = textNode('div','');
      for (const h of c.history) {
        const label = h.outcome === 1 ? 'Match won' : h.outcome === 0.5 ? 'Match drawn' : h.outcome === 0 ? 'Match lost' : 'Verified result';
        list.append(textNode('p',label+': '+h.before+' → '+h.after+' ('+(h.change>0?'+':'')+Number(h.change.toFixed(2))+')'));
      }
      if (!c.history.length) list.append(textNode('p',c.history_available?'No recent rating changes returned.':'Recent rating history is unavailable.','muted'));
      else list.append(textNode('small','Recent verified history only; this is not a lifetime wins/losses total.'));
      card.append(list); view.append(card);
    }
    const policy = engine.comparison?.ranking_policy, config = policy?.config;
    let policyText = 'Ratings and grades come from the shared server; comparison mode does not calculate or change them.';
    if (config?.grades?.length) policyText += ' Current grade minimums: '+config.grades.map(g => g.name+' '+g.minimum).join(', ')+'.';
    if (Number.isFinite(config?.k)) policyText += ' Current K-factor: '+config.k+'.';
    view.append(textNode('p',policyText,'muted'));
    for (const message of engine.comparison?.rating_errors || []) view.append(textNode('p',message,'muted'));
  }
  function comparisonNotice() {
    const view = document.getElementById('view');
    if (!view || view.querySelector('[data-comparison-notice]')) return;
    const item = textNode('p',explanation,'muted'); item.dataset.comparisonNotice = '1'; view.prepend(item);
  }
  function ready() {
    if (installed || typeof window.render !== 'function') return;
    installed = true;
    // The checkout's CSS already defines both themes. Server-published inline
    // overrides would hide the very interface differences being compared.
    window.applyPublishedTheme = function () {};
    const originalRender = window.render;
    window.render = function (...args) {
      const result = originalRender.apply(this,args); ratingDisplay(); comparisonNotice(); return result;
    };
    if (typeof window.studioView === 'function') {
      const originalStudio = window.studioView;
      window.studioView = async function (...args) {
        const result = await originalStudio.apply(this,args);
        const view = document.getElementById('view');
        if (view) for (const button of view.querySelectorAll('button')) if (button.textContent === 'Preview theme draft') {
          button.disabled = true; button.title = 'The X-Orbit comparison theme is preserved while you compare interfaces.';
        }
        comparisonNotice(); return result;
      };
    }
  }
  window.XOrbitComparison = Object.freeze({ready});
  document.addEventListener('DOMContentLoaded',ready,{once:true});
})();
