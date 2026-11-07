// Mount the actual FV library: state-only tests cannot detect its opening notification.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parse, compileScript, babelParse } from '@vue/compiler-sfc';
import { JSDOM } from 'jsdom';
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'https://www.creatorsn.com/'});
for(const key of ['window','document','Element','HTMLElement','SVGElement','Document','ShadowRoot','Node','Event','MouseEvent','MutationObserver'])globalThis[key]=dom.window[key];
globalThis.getComputedStyle=dom.window.getComputedStyle.bind(dom.window);
globalThis.requestAnimationFrame=callback=>setTimeout(callback,0);globalThis.cancelAnimationFrame=clearTimeout;
const Vue=await import('vue');
const Fluent=(await import('@creatorsn/vfluent3')).default;
function component(path,overrides={}) {
 const {descriptor}=parse(readFileSync(new URL('../src/'+path,import.meta.url),'utf8'));
 let code=compileScript(descriptor,{id:'mounted-'+path,inlineTemplate:true,genDefaultAs:'component'}).content;
 const nodes=babelParse(code,{sourceType:'module'}).program.body,imports={};
 for(const n of nodes)if(n.type==='ImportDeclaration')for(const spec of n.specifiers){
  const value=n.source.value==='vue'?Vue[spec.imported?.name||'default']:overrides[spec.local.name];
  assert.notEqual(value,undefined,`Missing import ${spec.local.name}`);imports[spec.local.name]=value;
 }
 for(const n of [...nodes].reverse())if(n.type==='ImportDeclaration')code=code.slice(0,n.start)+code.slice(n.end);
 return Function(...Object.keys(imports),code+';return component;')(...Object.values(imports));
}
const tick=async()=>{await Vue.nextTick();await Vue.nextTick();await new Promise(resolve=>setTimeout(resolve,10));await Vue.nextTick();};
const sample={client_id:'fixture-client',name:'Fixture',client_type:'public',enabled:true,description:'',redirect_uris:['https://example.org/callback']};
function button(root,text) {
 const match=[...root.querySelectorAll('.fv-Button')].find(e=>e.querySelector('.fv-btn-content-block')?.textContent.trim()===text);
 assert.ok(match,`Missing button ${text}`);return match;
}
function click(el) { el.dispatchEvent(new window.MouseEvent('click',{bubbles:true,cancelable:true})); }
test('real FV create/edit buttons keep panels open; cancel, validation and saves work',async()=>{
 const calls=[],errors=[];const theme=()=>({gradient:'linear-gradient(90deg,pink,purple)'});
 const editor=component('components/admin/ApplicationEditorPanel.vue',{useTheme:theme});
 const page=component('views/admin/AdminApplicationsView.vue',{ApplicationEditorPanel:editor,useTheme:theme,OIDCApi:{
  list:async()=>[sample],
  create:async body=>{calls.push(['create',body]);return {client_secret:'fixture-secret-not-real'};},
  update:async(id,body)=>{calls.push(['update',id,body]);return {};},
 }});
 const host=document.createElement('div');document.body.append(host);
 const app=Vue.createApp(page);app.use(Fluent);app.config.errorHandler=e=>errors.push(e);
 try {
  app.mount(host);await tick();
  const modal=()=>document.querySelector('.application-editor-modal');
  assert.equal(modal().style.display,'none');
  click(button(host,'添加应用'));await tick();
  assert.notEqual(modal().style.display,'none','opening notification must not close the editor');
  assert.equal(modal().parentElement,document.body,'panel must escape clipped scrolling ancestors');
  assert.equal(modal().querySelector('.panel-heading').textContent,'添加应用');
  click(button(modal(),'保存应用'));await tick();assert.equal(calls.length,0,'blank required fields must not save');
  const name=modal().querySelector('input:not([type=checkbox])');name.value='New fixture';name.dispatchEvent(new window.Event('input',{bubbles:true}));
  const redirects=modal().querySelector('textarea[required]');redirects.value='https://example.org/new';redirects.dispatchEvent(new window.Event('input',{bubbles:true}));
  await tick();click(button(modal(),'保存应用'));await tick();await tick();
  assert.equal(calls[0][0],'create');assert.equal(calls[0][1].name,'New fixture');assert.equal(modal().style.display,'none');
  const secret=document.querySelector('.application-secret-modal');assert.notEqual(secret.style.display,'none');assert.match(secret.textContent,/fixture-secret-not-real/);
  click(button(secret,'我已安全保存'));await tick();assert.equal(secret.style.display,'none');assert.doesNotMatch(secret.textContent,/fixture-secret-not-real/);
  click(button(host,'编辑'));await tick();assert.notEqual(modal().style.display,'none');assert.equal(modal().querySelector('.panel-heading').textContent,'修改应用');assert.equal(modal().querySelector('input:not([type=checkbox])').value,'Fixture');
  click(button(modal(),'保存应用'));await tick();await tick();assert.equal(calls[1][0],'update');assert.equal(calls[1][1],'fixture-client');
  click(button(host,'添加应用'));await tick();click(button(modal(),'取消'));await tick();assert.equal(modal().style.display,'none');
  assert.deepEqual(errors,[]);
 } finally {app.unmount();host.remove();await tick();}
});
test.after(()=>dom.window.close());
