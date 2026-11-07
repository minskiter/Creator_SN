import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { reactive, h } from 'vue';
import { parse, compileScript, compileTemplate, babelParse } from '@vue/compiler-sfc';
import postcss from 'postcss';
const viewPath = 'views/admin/AdminUsersView.vue', panelPath = 'components/admin/UserRolePanel.vue';
const read = path => readFileSync(new URL('../src/' + path, import.meta.url), 'utf8');
function component(path, api = {}) {
  const { descriptor } = parse(read(path));
  let code = compileScript(descriptor, { id: path, genDefaultAs: 'component' }).content;
  const nodes = babelParse(code, { sourceType: 'module' }).program.body;
  for (const node of [...nodes].reverse()) if (node.type === 'ImportDeclaration') code = code.slice(0, node.start) + code.slice(node.end);
  const imports = { h, UserApi: api, UserRolePanel: {}, useTheme: () => ({}), mapState: () => ({}), useAppStore: () => ({ local: (text, params = {}) => Object.entries(params).reduce((s, [k,v]) => s.replaceAll(`{${k}}`, v), text) }) };
  return Function(...Object.keys(imports), code + ';return component;')(...Object.values(imports));
}
function instance(path, api = {}, props = {}) {
  const options = component(path, api), events = [], warnings = [];
  const vm = reactive({ ...options.data(), ...props, $emit: (...args) => events.push(args), $barWarning: (...args) => warnings.push(args), $infoBox: (_message, options) => options.confirm() });
  for (const [key, fn] of Object.entries(options.methods)) vm[key] = fn.bind(vm);
  for (const [key, fn] of Object.entries(options.computed || {})) Object.defineProperty(vm, key, typeof fn === 'function' ? { get: () => fn.call(vm) } : { get: () => fn.get.call(vm), set: v => fn.set.call(vm, v) });
  return { vm, options, events, warnings };
}
const roles = [{ id: 'user', name: 'User' }, { id: 'admin', name: 'Admin' }];
function panel(api = {}, role = 'user') {
  const result = instance(panelPath, api, { user: { userid: 'test-member', role }, roles, modelValue: true, loading: false, error: '' });
  result.vm.syncRoles(); return result;
}
function styles(path) { return postcss.parse(parse(read(path)).descriptor.styles[0].content); }
test('user list and role panel compile without template errors', () => {
  for (const path of [viewPath, panelPath]) {
    const { descriptor, errors } = parse(read(path)); assert.deepEqual(errors, []);
    const result = compileTemplate({ source: descriptor.template.content, filename: path, id: path }); assert.deepEqual(result.errors, []);
  }
});
test('mobile layout provides visible role chips and permission buttons instead of a wide table', () => {
  const source = read(viewPath);
  assert.match(source, /class="mobile-users"/); assert.match(source, /class="mobile-user-roles"/);
  assert.match(source, /class="touch-button permission-button"/);
  assert.doesNotMatch(source, /min-width:\s*1100px/);
  let hidden = false, cards = false;
  styles(viewPath).walkAtRules('media', media => {
    if (media.params === '(max-width: 1024px)') media.walkRules(rule => {
      if (rule.selector.includes('.list-card')) rule.walkDecls('display', d => hidden ||= d.value === 'none');
      if (rule.selector === '.mobile-users') rule.walkDecls('display', d => cards ||= d.value === 'grid');
    });
  });
  assert.ok(hidden && cards);
});
test('touch controls and pagination fit narrow viewports without hiding actions', () => {
  assert.match(read(viewPath), /class="mobile-pagination"/);
  assert.match(read(viewPath), /grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\)/);
  assert.match(read(viewPath), /@media \(max-width: 360px\)/);
  assert.match(read(viewPath), /overflow-wrap: anywhere/);
  styles(viewPath).walkRules('.touch-button', rule => {
    const min = rule.nodes.find(n => n.prop === 'min-height'); assert.equal(min.value, '44px');
  });
});
test('role panel is viewport-bounded, independently scrollable, and uses labeled native checkboxes', () => {
  const source = read(panelPath);
  assert.match(source, /width="min\(560px, calc\(100vw - 24px\)\)"/);
  assert.match(source, /height="min\(600px, calc\(100dvh - 24px\)\)"/);
  assert.match(source, /overflow-y: auto/); assert.match(source, /flex-shrink: 0/);
  assert.match(source, /<label v-for="role in roles"/); assert.match(source, /type="checkbox"/);
  assert.match(source, /@change="toggle\(role, \$event.target.checked, \$event.target\)"/);
  assert.doesNotMatch(source, /<fv-check-box|@click="toggle/);
});
test('role sync trims tokens and never confuses admin with an admin-like role', () => {
  const { vm } = panel({}, ' user, superadmin, ');
  assert.deepEqual(vm.roleStates, { user: true, admin: false });
});
test('grant sends an explicit true state and persists the server role', async () => {
  const calls = [];
  const { vm, events } = panel({ addRole: async (...args) => { calls.push(args); return { code: 200, data: { role: 'user,admin' } }; } });
  await vm.toggle(roles[1], true);
  assert.deepEqual(calls, [['test-member', 'admin']]); assert.equal(vm.user.role, 'user,admin');
  assert.equal(vm.roleStates.admin, true); assert.deepEqual(events, [['updated']]); assert.equal(vm.busy, false);
});
test('removing the last role correctly persists an empty server value', async () => {
  const { vm } = panel({ removeRole: async () => ({ code: 200, data: { role: '' } }) }, 'admin');
  await vm.toggle(roles[1], false);
  assert.equal(vm.user.role, ''); assert.deepEqual(vm.roleStates, { user: false, admin: false });
});
test('null role and omitted role responses do not retain a removed role', async () => {
  for (const data of [{ role: null }, {}]) {
    const { vm } = panel({ removeRole: async () => ({ code: 200, data }) }, 'admin');
    await vm.toggle(roles[1], false); assert.equal(vm.user.role, '');
  }
});
test('failed permission update restores checkbox state and shows an inline error', async () => {
  const { vm, events } = panel({ addRole: async () => ({ code: 403, message: 'Permission denied' }) });
  await vm.toggle(roles[1], true);
  assert.equal(vm.user.role, 'user'); assert.equal(vm.roleStates.admin, false); assert.equal(vm.errorMessage, 'Permission denied');
  assert.equal(vm.busy, false); assert.equal(events.length, 0);
});
test('pending update blocks duplicate changes and dismissal', async () => {
  let finish, calls = 0;
  const { vm, events } = panel({ addRole: () => { calls++; return new Promise(resolve => finish = resolve); } });
  const pending = vm.toggle(roles[1], true); await Promise.resolve(); assert.equal(vm.busy, true);
  await vm.toggle(roles[0], false); vm.close(); assert.equal(calls, 1); assert.equal(events.length, 0);
  finish({ code: 200, data: { role: 'user,admin' } }); await pending;
  vm.close(); assert.deepEqual(events, [['updated'], ['update:modelValue', false]]);
});
test('late response cannot apply another account role to the current account', async () => {
  let finish;
  const { vm } = panel({ addRole: () => new Promise(resolve => finish = resolve) });
  const old = vm.user, pending = vm.toggle(roles[1], true); await Promise.resolve();
  vm.user = { userid: 'other-member', role: 'user' }; vm.syncRoles();
  finish({ code: 200, data: { role: 'user,admin' } }); await pending;
  assert.equal(old.role, 'user,admin'); assert.equal(vm.user.role, 'user'); assert.equal(vm.roleStates.admin, false);
});
test('unknown role, missing account, load errors and non-boolean events cannot write permissions', async () => {
  const { vm } = panel({ addRole: async () => { throw Error('Unexpected API write'); } });
  await vm.toggle({ id: 'unknown' }, true); await vm.toggle(roles[1], {});
  vm.loading = true; await vm.toggle(roles[1], true); vm.loading = false;
  vm.error = 'Failed'; await vm.toggle(roles[1], true); vm.error = ''; vm.user.userid = ''; await vm.toggle(roles[1], true);
  assert.equal(vm.busy, false); assert.equal(vm.roleStates.admin, false);
});
test('role request failures are visible and a subsequent retry succeeds', async () => {
  let fail = true;
  const { vm } = instance(viewPath, { roles: async () => { if (fail) throw Error('Offline'); return { code: 200, data: roles }; } });
  await vm.getRoles(); assert.equal(vm.rolesError, 'Offline'); assert.equal(vm.rolesLoading, false);
  fail = false; await vm.getRoles(); assert.equal(vm.rolesError, ''); assert.equal(vm.roles.length, 2);
});
test('list refresh updates the open user and ignores out-of-order requests', async () => {
  let finish;
  const { vm } = instance(viewPath, { list: () => new Promise(resolve => finish = resolve), count: async () => ({ code: 200, data: 1 }) });
  const first = vm.getUsers(), firstFinish = finish;
  const second = vm.getUsers(), secondFinish = finish;
  vm.showUserRole({ userid: 'test-member', role: 'user' });
  secondFinish({ code: 200, data: [{ userid: 'test-member', role: 'admin' }] }); await second;
  firstFinish({ code: 200, data: [] }); await first;
  assert.equal(vm.users.length, 1); assert.equal(vm.currentItem.role, 'admin'); assert.equal(vm.loading, false);
});
test('mobile pagination respects bounds and existing backend pagination', () => {
  const { vm } = instance(viewPath); let loads = 0; vm.getUsers = () => loads++; vm.total = 21;
  vm.handlePageChange(0); vm.handlePageChange(4); assert.equal(loads, 0);
  vm.handlePageChange(2); assert.equal(vm.page, 2); assert.equal(loads, 1);
  vm.loading = true; vm.handlePageChange(3); assert.equal(vm.page, 2);
  assert.deepEqual(vm.roleNames('user, admin, '), ['user', 'admin']);
});
test('administrator removal requires FV confirmation, names the account, and never writes on cancel', async () => {
  let dialog, message, calls = 0;
  const { vm, events } = panel({ removeRole: async () => { calls++; return { code: 200, data: { role: 'user' } }; } }, 'user,admin');
  vm.$infoBox = (content, options) => { message = content.children; dialog = options; };
  const input = { checked: false }, pending = vm.toggle(roles[1], false, input);
  assert.equal(calls, 0); assert.equal(input.checked, true); assert.equal(vm.roleStates.admin, true);
  assert.equal(vm.user.role, 'user,admin'); assert.equal(vm.busy, true);
  assert.match(message, /test-member/); assert.match(message, /Administrator \(admin\)/); assert.match(message, /lose administrator access/);
  assert.equal(dialog.title, 'Confirm administrator permission change');
  assert.equal(dialog.confirmTitle, 'Confirm removal'); assert.equal(dialog.status, 'warning');
  vm.close(); await vm.toggle(roles[0], false); assert.equal(events.length, 0);
  dialog.cancel(); await pending;
  assert.equal(calls, 0); assert.equal(vm.busy, false); assert.equal(vm.roleStates.admin, true); assert.equal(events.length, 0);
});
test('explicit confirmation is required for grant, removal, and edits to an administrator regular role', async () => {
  for (const [current, role, enabled] of [['user', roles[1], true], ['user,admin', roles[1], false], ['user,admin', roles[0], false]]) {
    let dialog, calls = 0;
    const update = async () => { calls++; return { code: 200, data: {} }; };
    const { vm } = panel({ addRole: update, removeRole: update }, current);
    vm.$infoBox = (_text, options) => { dialog = options; };
    const pending = vm.toggle(role, enabled);
    assert.equal(calls, 0); dialog.confirm(); await pending; assert.equal(calls, 1);
    await dialog.confirm(); assert.equal(calls, 1);
    assert.equal(vm.roleStates[role.id], enabled);
  }
});
test('a stale confirmation cannot change a different account, externally changed roles, or a closed panel', async () => {
  for (const mutate of [vm => { vm.user = { userid: 'other', role: 'user' }; }, vm => { vm.user.role = ''; }, vm => { vm.modelValue = false; }]) {
    let dialog, calls = 0;
    const { vm } = panel({ addRole: async () => { calls++; return { code: 200, data: {} }; } });
    vm.$infoBox = (_text, options) => { dialog = options; };
    const pending = vm.toggle(roles[1], true); mutate(vm); dialog.confirm(); await pending;
    assert.equal(calls, 0); assert.equal(vm.busy, false);
  }
});
test('confirmation component failure fails closed without granting privileges', async () => {
  let calls = 0;
  const { vm } = panel({ addRole: async () => { calls++; return { code: 200 }; } });
  vm.$infoBox = () => { throw Error('Dialog unavailable'); };
  await vm.toggle(roles[1], true);
  assert.equal(calls, 0); assert.equal(vm.roleStates.admin, false); assert.equal(vm.busy, false);
  assert.equal(vm.errorMessage, 'Dialog unavailable');
});
test('FV confirmation text wraps long identities and keeps mobile actions touch-sized', () => {
  const source = read(panelPath);
  assert.match(source, /h\('span', \{ class: 'role-change-confirm-message' \}, message\)/);
  assert.match(source, /\.fv-InfoBox:has\(\.role-change-confirm-message\)/);
  assert.match(source, /min-width: 0; width: 480px; max-width: 100%/);
  assert.match(source, /white-space: pre-line; overflow-wrap: anywhere/);
  assert.match(source, /\.info-box-control-block \.fv-button \{ min-height: 44px/);
});
