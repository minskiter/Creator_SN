import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parse, compileScript, compileTemplate, babelParse } from '@vue/compiler-sfc';
import { computed, reactive, ref } from 'vue';
import postcss from 'postcss';
const read = path => readFileSync(new URL('../src/' + path, import.meta.url), 'utf8');
const viewPath = 'views/admin/AdminApplicationsView.vue';
const panelPath = 'components/admin/ApplicationEditorPanel.vue';
function setup(path, imports = {}, props = {}, emit = () => {}) {
  const { descriptor } = parse(read(path));
  let code = compileScript(descriptor, { id: 'applications-test', genDefaultAs: 'component' }).content;
  const nodes = babelParse(code, { sourceType: 'module' }).program.body;
  for (const node of [...nodes].reverse()) if (node.type === 'ImportDeclaration') code = code.slice(0, node.start) + code.slice(node.end);
  let mounted;
  const values = { computed, reactive, ref, onMounted: fn => mounted = fn, useTheme: () => ({ gradient: 'test-gradient' }), ApplicationEditorPanel: {}, ...imports };
  const component = Function(...Object.keys(values), code + ';return component;')(...Object.values(values));
  const state = component.setup(props, { expose() {}, emit });
  return { state, mount: () => mounted?.() };
}
const application = { name: 'Gateway', description: 'Proxy management', client_id: 'test-client', client_type: 'confidential', enabled: true, redirect_uris: ['https://example.org/callback'] };
function view(overrides = {}) {
  const calls = [];
  const api = {
    list: async () => [{ ...application }],
    create: async body => { calls.push(['create', body]); return { client_secret: 'test-only-secret' }; },
    update: async (id, body) => { calls.push(['update', id, body]); return {}; },
    ...overrides,
  };
  return { ...setup(viewPath, { OIDCApi: api }), calls };
}
function declarations(path, selector, media = false) {
  const { descriptor } = parse(read(path));
  const result = {};
  postcss.parse(descriptor.styles[0].content).walkRules(selector, rule => {
    if ((rule.parent.type === 'atrule') !== media) return;
    rule.walkDecls(d => result[d.prop] = d.value);
  });
  return result;
}
test('application and editor templates compile with scoped styles', () => {
  for (const path of [viewPath, panelPath]) {
    const { descriptor, errors } = parse(read(path));
    assert.deepEqual(errors, []);
    const script = compileScript(descriptor, { id: path });
    const template = compileTemplate({ source: descriptor.template.content, filename: path, id: path, compilerOptions: { bindingMetadata: script.bindings } });
    assert.deepEqual(template.errors, []);
    assert.ok(descriptor.styles.every(s => s.scoped));
  }
});
test('page spacing and typography match project management', () => {
  const project = 'views/admin/AdminProjectsView.vue';
  const actual = declarations(viewPath, '.applications-page');
  const reference = declarations(project, '.projects-page');
  for (const key of ['position', 'flex', 'min-width', 'height', 'overflow', 'padding', 'color', 'font-family']) assert.equal(actual[key], reference[key]);
  for (const key of ['font-size', 'margin']) assert.equal(declarations(viewPath, '.page-header h1')[key], declarations(project, '.page-header h1')[key]);
  assert.match(read(viewPath), /<fv-text-box/);
});
test('long identifiers and callback URLs cannot force the grid wider', () => {
  assert.equal(declarations(viewPath, '.application-admin-card')['grid-template-columns'], '72px minmax(0, 1fr) auto');
  assert.match(read(viewPath), /overflow-wrap: anywhere/);
  assert.match(read(viewPath), /@media \(max-width: 720px\)/);
  assert.match(read(viewPath), /\.application-details \{ grid-column: 1 \/ -1; \}/);
  assert.equal(declarations(viewPath, '.application-actions')['flex-wrap'], 'wrap');
});
test('edit and single-use secret use Fluent panels rather than native dialogs', () => {
  assert.doesNotMatch(read(viewPath), /<dialog|showModal\(/);
  for (const path of [viewPath, panelPath]) {
    assert.match(read(path), /<fv-panel/);
    assert.match(read(path), /:is-central-side="true"/);
    assert.match(read(path), /calc\(100dvh - 32px\)/);
  }
  assert.match(read(viewPath), /:show-title-bar="false"/);
  assert.match(read(panelPath), /reportValidity|requestSubmit/);
  assert.match(read(panelPath), /:disabled="editing \|\| saving"/);
});
test('initial load and client-side search preserve name, ID and callback filtering', async () => {
  const { state: s, mount } = view(); await mount();
  assert.equal(s.apps.value.length, 1); assert.equal(s.busy.value, false);
  for (const text of ['gateway', 'TEST-CLIENT', 'example.org/callback']) { s.search.value = text; assert.equal(s.filtered.value.length, 1); }
  s.search.value = 'no-match'; assert.equal(s.filtered.value.length, 0);
});
test('create preserves validation, normalizes callbacks and shows secret once', async () => {
  const { state: s, calls } = view(); s.edit();
  assert.equal(s.editorVisible.value, true);
  s.editor.value = { reportValidity: () => false }; await s.save(); assert.equal(calls.length, 0);
  s.editor.value = { reportValidity: () => true };
  Object.assign(s.form, { name: 'New', description: 'Test', client_type: 'confidential', enabled: true });
  s.redirects.value = ' https://example.org/a \n\nhttps://example.org/b\n';
  await s.save();
  assert.equal(calls[0][0], 'create'); assert.deepEqual(calls[0][1].redirect_uris, ['https://example.org/a', 'https://example.org/b']);
  assert.equal(s.editorVisible.value, false); assert.equal(s.secretVisible.value, true);
  assert.equal(s.newSecret.value, 'test-only-secret');
  s.closeSecret(); assert.equal(s.newSecret.value, ''); assert.equal(s.secretVisible.value, false);
});
test('editing updates the existing client without creating another registration', async () => {
  const { state: s, calls } = view(); s.edit(application);
  s.editor.value = { reportValidity: () => true }; s.form.name = 'Updated'; await s.save();
  assert.equal(calls[0][0], 'update'); assert.equal(calls[0][1], application.client_id);
  assert.equal(calls[0][2].name, 'Updated'); assert.equal(s.secretVisible.value, false);
});
test('API failure keeps editor open and exposes the validation error', async () => {
  const { state: s } = view({ create: async () => { throw { response: { data: { detail: 'Invalid callback' } } }; } });
  s.edit(); s.editor.value = { reportValidity: () => true }; await s.save();
  assert.equal(s.editorVisible.value, true); assert.equal(s.editorError.value, 'Invalid callback'); assert.equal(s.busy.value, false);
});
test('busy state prevents concurrent list requests and editor dismissal', async () => {
  const { state: s, calls } = view({ list: async () => { throw Error('Must not load'); } });
  s.edit(); s.busy.value = true; s.setEditorVisible(false); await s.load(); await s.save();
  assert.equal(s.editorVisible.value, true); assert.equal(calls.length, 0); assert.equal(s.error.value, '');
});
test('editor keeps native form validation and blocks submit/close while saving', () => {
  const props = reactive({ form: {}, saving: false }); const events = [];
  const { state: s } = setup(panelPath, {}, props, (...args) => events.push(args));
  let submitted = 0; s.editorForm.value = { requestSubmit: () => submitted++, reportValidity: () => true };
  assert.equal(s.reportValidity(), true); s.submit(); assert.equal(submitted, 1);
  props.saving = true; s.submit(); s.close(); assert.equal(submitted, 1); assert.equal(events.length, 0);
  props.saving = false; s.close(); assert.deepEqual(events, [['update:modelValue', false]]);
});
test('FV opening notification stays open instead of being interpreted as close', () => {
  const props = reactive({ form: {}, saving: false }); const events = [];
  const { state: s } = setup(panelPath, {}, props, (...args) => events.push(args));
  assert.match(read(panelPath), /@update:model-value="setVisible"/);
  assert.doesNotMatch(read(panelPath), /@update:model-value="close"/);
  s.setVisible(true); assert.deepEqual(events, [['update:modelValue', true]]);
  s.setVisible(false); assert.deepEqual(events.at(-1), ['update:modelValue', false]);
  props.saving = true; s.setVisible(false); assert.equal(events.length, 2);
});
test('missing editor refs fail validation safely and panels escape clipped page containers', async () => {
  const { state: s, calls } = view(); await s.save(); assert.equal(calls.length, 0);
  const { state: editor } = setup(panelPath, {}, { form: {}, saving: false });
  assert.equal(editor.reportValidity(), false); editor.submit();
  for (const path of [viewPath, panelPath]) assert.match(read(path), /<Teleport to="body">/);
  assert.match(read(panelPath), /overflow-y: auto/);
  assert.match(read(panelPath), /flex-shrink: 0/);
});
