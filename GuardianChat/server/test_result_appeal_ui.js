'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {Element,walk,content}=require('./browser-test-dom.cjs');
const requests=[],root=new Element();let refreshed=0;
const summary={review:{state:'needs_human',stage:'video',policy:'local-ocr-conservative-v2',reason:'Conflicting readings'},limitation:'OCR does not establish authenticity.',reports:[{uid:'a',score_a:3,score_b:1}],findings:[{uid:'a',stage:'video',analysis:{score:null,reason:'Inconclusive',text:'<script>untrusted OCR</script>'}}],appeals:[{uid:'a',reason:'Please review the result.',state:'open'}],retention:{evidence_held:true}};
const context={resultRoom(){},evidenceForm(){},report(){},reviewOpen:async()=>{},review(){},node:(tag,text='',cls='')=>{const n=new Element(tag,text);n.className=cls;return n},button:(text,fn)=>{const b=new Element('button',text);b.onclick=fn;return b},input:(parent,label,name)=>{const n=new Element('input');n.name=name;parent.append(n);return n},$:()=>root,api:async(path,body)=>{requests.push({path,body});return path.startsWith('/gamebox/review-summary')?summary:{ok:true}},Date,encodeURIComponent};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/private-results.js','utf8'),context);

/** Exercise user/admin forms without camera or real publication.
 * @returns {Promise<void>} Rejects on failed UI assertions.
 */
async function run(){
 const panel=new Element();context.appendResultAppeal(panel,{id:'match',evidence_review:{can_appeal:true,appeal_until:Date.now()/1000+1000}},async()=>{refreshed++});
 const launch=walk(panel).find(n=>n.textContent==='Request review / appeal');launch.onclick();
 const form=walk(panel).find(n=>n.tagName==='FORM'),reason=walk(form).find(n=>n.name==='reason');reason.value='Please check the exact score.';
 await form.onsubmit({preventDefault(){}});await form.onsubmit({preventDefault(){}});
 assert.equal(refreshed,1);assert.equal(requests.filter(r=>r.path==='/gamebox/evidence_appeal').length,1);assert.equal(requests[0].body.room,'match');
 const closed=new Element();context.appendResultAppeal(closed,{evidence_review:{can_appeal:false}},async()=>{});assert(!walk(closed).some(n=>n.tagName==='BUTTON'));
 await context.appendReviewSummary(root,{id:'match'});assert.match(content(root),/Inconclusive/);assert.match(content(root),/cleanup is paused/);assert(!walk(root).some(n=>n.tagName==='SCRIPT'),'OCR is rendered as text, never HTML');
 const decision=walk(root).find(n=>n.tagName==='FORM'),select=walk(decision).find(n=>n.tagName==='SELECT');select.value='correction_required';walk(decision).find(n=>n.name==='reason').value='Evidence needs an audited correction.';
 await decision.onsubmit({preventDefault(){}});assert.equal(requests.at(-1).path,'/gamebox/evidence_appeal_decide');assert.equal(requests.at(-1).body.outcome,'correction_required');assert(!('score' in requests.at(-1).body));
 console.log('Appeal filing, duplicate-click guard, private findings, text-only OCR and audited correction hold UI passed.');
}
run().catch(error=>{console.error(error);process.exitCode=1});
