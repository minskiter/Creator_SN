import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { reactive } from 'vue';
import { parse, compileScript, compileTemplate, babelParse } from '@vue/compiler-sfc';
import postcss from 'postcss';
const viewPath='views/admin/AdminResumesView.vue', panelPath='components/admin/ResumeEditorPanel.vue';
const read=path=>readFileSync(new URL('../src/'+path,import.meta.url),'utf8');
const local=(text,params={})=>Object.entries(params).reduce((s,[k,v])=>s.replaceAll(`{${k}}`,v),text);
function instance(path,apis={},props={}) {
 const {descriptor}=parse(read(path));let code=compileScript(descriptor,{id:path,genDefaultAs:'component'}).content;
 const nodes=babelParse(code,{sourceType:'module'}).program.body;
 for(const n of [...nodes].reverse())if(n.type==='ImportDeclaration')code=code.slice(0,n.start)+code.slice(n.end);
 const values={ResumeEditorPanel:{},ResumeApi:apis,UserApi:{list:async()=>({code:200,data:[]})},useAppStore:()=>({local}),useTheme:()=>({}),mapState:()=>({}),createResumeImageInterceptor:()=>()=>{},handlePowerEditorImageDrop:()=>{},handlePowerEditorImagePaste:()=>{}};
 const options=Function(...Object.keys(values),code+';return component;')(...Object.values(values));
 const events=[],warnings=[],dialogs=[];
 const vm=reactive({...options.data?.(),...props,$emit:(...args)=>events.push(args),$barWarning:(...args)=>warnings.push(args),$infoBox:(text,options)=>dialogs.push({text,...options})});
 for(const [key,fn] of Object.entries(options.methods))vm[key]=fn.bind(vm);
 for(const [key,fn] of Object.entries(options.computed||{}))Object.defineProperty(vm,key,typeof fn==='function'?{get:()=>fn.call(vm)}:{get:()=>fn.get.call(vm),set:v=>fn.set.call(vm,v)});
 return {vm,events,warnings,dialogs};
}
test('resume list and editor compile with mobile card layout and native mobile account selection',()=>{
 for(const path of [viewPath,panelPath]){
  const {descriptor,errors}=parse(read(path));assert.deepEqual(errors,[]);
  const result=compileTemplate({source:descriptor.template.content,filename:path,id:path});assert.deepEqual(result.errors,[]);
 }
 const view=read(viewPath);assert.match(view,/class="mobile-resumes"/);assert.match(view,/class="mobile-resume-actions"/);assert.match(view,/overflow-wrap: anywhere/);
 const styles=postcss.parse(parse(view).descriptor.styles[0].content);let hidden=false,cards=false;
 styles.walkAtRules('media',media=>{if(media.params==='(max-width: 1024px)')media.walkRules(rule=>{
  if(rule.selector==='.list-card')rule.walkDecls('display',d=>hidden ||= d.value==='none');
  if(rule.selector==='.mobile-resumes')rule.walkDecls('display',d=>cards ||= d.value==='grid');
 });});assert.ok(hidden && cards);
 assert.match(view,/min-height: 44px/);assert.match(view,/@media \(max-width: 360px\)/);
 const panel=read(panelPath);assert.match(panel,/<Teleport to="body">/);assert.match(panel,/100dvh/);assert.match(panel,/min-height: 0/);assert.match(panel,/overflow-y: auto/);assert.match(panel,/flex-shrink: 0/);assert.match(panel,/<select class="mobile-user-picker"/);
 assert.doesNotMatch(panel,/\.editor-panel power-editor/);
});
test('resume load errors are visible and refresh recovers without losing data',async()=>{
 let failed=true;const {vm}=instance(viewPath,{list:async()=>{if(failed)throw Error('Offline');return {code:200,data:[{id:7}]};}});
 vm.resumes=[{id:3}];await vm.load();assert.equal(vm.loadError,'Offline');assert.deepEqual(vm.resumes,[{id:3}]);assert.equal(vm.loading,false);
 failed=false;await vm.load();assert.equal(vm.loadError,'');assert.deepEqual(vm.resumes,[{id:7}]);
});
test('create/edit initialize independent forms and cannot switch while saving',()=>{
 const {vm}=instance(viewPath);vm.userOptions=[{value:'',text:'Unbound'},{value:'member',text:'Member'}];
 vm.openCreate();assert.equal(vm.visible,true);assert.equal(vm.editing,false);assert.equal(vm.form.userid,'');
 vm.openEdit({id:7,userid:'member',introduction:{type:'doc'}});assert.equal(vm.editing,true);assert.equal(vm.form.id,7);assert.equal(vm.userOption.value,'member');
 vm.saving=true;vm.openCreate();assert.equal(vm.form.id,7);
});
test('opening before account options load preserves the existing bound account',()=>{
 const {vm}=instance(viewPath);vm.openCreate();assert.equal(vm.userOption.value,'');
 vm.openEdit({id:7,userid:'not-yet-loaded'});assert.equal(vm.userOption.value,'not-yet-loaded');
 assert.equal(vm.form.userid,'not-yet-loaded');assert.match(read(panelPath),/!userOptions.some/);
});
test('save failures leave the editor open and duplicate saves are blocked',async()=>{
 let finish,calls=0;const {vm,warnings}=instance(viewPath,{save:()=>{calls++;return new Promise(resolve=>finish=resolve);}});
 vm.visible=true;const pending=vm.save();await vm.save();assert.equal(calls,1);
 finish({code:403,message:'Denied'});await pending;assert.equal(vm.visible,true);assert.equal(vm.saving,false);assert.equal(warnings[0][0],'Denied');
});
test('delete still requires FV confirmation and targets the chosen resume only',async()=>{
 const calls=[];const {vm,dialogs}=instance(viewPath,{remove:async id=>{calls.push(id);return {code:200};},list:async()=>({code:200,data:[]})});
 await vm.remove({id:17});assert.equal(calls.length,0);assert.equal(dialogs.length,1);await dialogs[0].confirm();assert.deepEqual(calls,[17]);assert.equal(vm.saving,false);
});
test('mobile account selection emits the matching option and respects the saving guard',()=>{
 const options=[{key:'',value:'',text:'Unbound'},{key:'member',value:'member',text:'Member'}];
 const {vm,events}=instance(panelPath,{}, {modelValue:true,saving:false,userOptions:options,form:{userid:''}});
 vm.chooseNativeUser('member');assert.deepEqual(events,[['update:userOption',options[1]],['choose-user',options[1]]]);
 vm.chooseNativeUser('unknown');assert.equal(events.length,2);
 vm.saving=true;vm.chooseNativeUser('');vm.visible=false;assert.equal(events.length,2);
 vm.saving=false;vm.visible=false;assert.deepEqual(events.at(-1),['update:modelValue',false]);
});
