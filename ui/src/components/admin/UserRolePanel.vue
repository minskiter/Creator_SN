<template>
  <fv-panel v-model="visible" class="user-role-modal" theme="light" :title="local('User roles')" width="min(560px, calc(100vw - 24px))" height="min(600px, calc(100dvh - 24px))" background="rgba(255,255,255,.96)" :is-central-side="true" :is-acrylic="true" :is-footer="true">
    <template #header><h2 class="role-title">{{ local('User roles') }}</h2><button type="button" class="panel-button" :disabled="busy" @click="close">{{ local('Close') }}</button></template>
    <template #container>
      <div class="role-panel" @keydown.esc.stop.prevent="close" :aria-busy="busy || loading">
        <div class="role-user"><span class="avatar-letter">{{ letter }}</span><div class="role-identity"><strong>{{ user.userid }}</strong><small>{{ user.email || local('Creator SN user') }}</small></div></div>
        <p class="panel-caption">{{ local('Grant regular-user and administrator roles separately') }}<br>{{ local('Role changes are saved only after confirmation') }}</p>
        <p v-if="loading" class="panel-status" role="status">{{ local('Loading…') }}</p>
        <div v-else-if="error || !roles.length" class="role-load-error" role="alert"><p>{{ error || local('No roles available') }}</p><button type="button" class="panel-button" :disabled="busy" @click="$emit('retry')">{{ local('Retry') }}</button></div>
        <template v-else>
          <label v-for="role in roles" :key="role.id" class="role-item">
            <input class="role-checkbox" type="checkbox" :checked="Boolean(roleStates[role.id])" :style="{ accentColor: color }" :disabled="busy || !user.userid" @change="toggle(role, $event.target.checked, $event.target)" />
            <span class="role-copy"><strong>{{ role.id === 'admin' ? local('Administrator') : role.id === 'user' ? local('Regular user') : role.name || role.id }} <code>{{ role.id }}</code></strong><span>{{ role.id === 'admin' ? local('Can access the admin console and manage user permissions') : role.id === 'user' ? local('Can use Creator SN basic services') : role.name || role.id }}</span></span>
          </label>
        </template>
        <p v-if="errorMessage" class="role-error" role="alert">{{ errorMessage }}</p>
        <p class="panel-status" role="status" aria-live="polite">{{ progressMessage }}</p>
      </div>
    </template>
    <template #footer><button type="button" class="panel-button panel-primary" :style="{ background: gradient }" :disabled="busy" @click="close">{{ busy ? progressMessage : local('Done') }}</button></template>
  </fv-panel>
</template>
<script>
import { UserApi } from '@/api';
import { useAppStore } from '@/store';
import { mapState } from 'pinia';
import { useTheme } from '@/stores/useTheme';
import { h } from 'vue';
export default {
  name: 'UserRolePanel',
  props: {
    modelValue: { default: false }, user: { default: () => ({}) }, roles: { default: () => [] },
    loading: { type: Boolean, default: false }, error: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'updated', 'retry'],
  data() { return { busy: false, confirming: false, roleStates: {}, errorMessage: '', statusMessage: '' }; },
  computed: {
    ...mapState(useTheme, ['theme', 'color', 'gradient']),
    visible: {
      get() { return this.modelValue; },
      set(value) { if (!this.busy) this.$emit('update:modelValue', value); },
    },
    letter() { return (this.user.name || this.user.userid || '?').slice(0, 1).toUpperCase(); },
    progressMessage() { return this.busy ? this.local(this.confirming ? 'Awaiting confirmation…' : 'Saving…') : this.statusMessage; },
  },
  watch: {
    user: { immediate: true, handler() { this.syncRoles(); this.errorMessage = ''; this.statusMessage = ''; } },
    roles: { deep: true, handler() { this.syncRoles(); } },
    modelValue(value) { if (value) { this.syncRoles(); this.errorMessage = ''; this.statusMessage = ''; } },
  },
  methods: {
    local(text, params) { return useAppStore().local(text, params); },
    close() { if (!this.busy) this.visible = false; },
    syncRoles() {
      const current = String(this.user.role || '').split(',').map(role => role.trim()).filter(Boolean);
      this.roleStates = Object.fromEntries(this.roles.map(role => [role.id, current.includes(role.id)]));
    },
    confirmChange(userid, role, enabled) {
      const action = enabled ? 'Grant role' : 'Remove role';
      const roleName = role.id === 'admin' ? this.local('Administrator') : role.id === 'user' ? this.local('Regular user') : role.name || role.id;
      let message = this.local('Confirm {action} for {userid}: {role}?', { action: this.local(action), userid, role: `${roleName} (${role.id})` });
      if (role.id === 'admin') message += '\n' + this.local(enabled ? 'This account will be able to manage users and administrator permissions.' : 'This account will lose administrator access. If this is your account, you may be unable to manage the site.');
      return new Promise(resolve => {
        this.$infoBox(h('span', { class: 'role-change-confirm-message' }, message), {
          theme: this.theme,
          title: this.local(role.id === 'admin' ? 'Confirm administrator permission change' : 'Confirm permission change'),
          status: 'warning',
          confirmTitle: this.local(enabled ? 'Confirm grant' : 'Confirm removal'),
          cancelTitle: this.local('Cancel'),
          confirm: () => resolve(true),
          cancel: () => resolve(false),
        });
      });
    },
    async toggle(role, enabled, input) {
      // Native checkboxes toggle before @change; keep the saved state visible until confirmed.
      if (input) input.checked = Boolean(this.roleStates[role.id]);
      if (this.busy || this.loading || this.error || !this.user.userid || typeof enabled !== 'boolean' || !this.roles.some(item => item.id === role.id)) return;
      if (Boolean(this.roleStates[role.id]) === enabled) return;
      const target = this.user, userid = target.userid, originalRole = target.role;
      this.busy = true; this.confirming = true; this.errorMessage = ''; this.statusMessage = '';
      try {
        if (!await this.confirmChange(userid, role, enabled)) return;
        this.confirming = false;
        // Never apply a stale confirmation to a different account or changed permissions.
        if (!this.modelValue || this.user.userid !== userid || this.user.role !== originalRole || this.loading || this.error || !this.roles.some(item => item.id === role.id)) {
          this.syncRoles();
          return;
        }
        this.roleStates = { ...this.roleStates, [role.id]: enabled };
        const result = enabled ? await UserApi.addRole(userid, role.id) : await UserApi.removeRole(userid, role.id);
        if (result.code !== 200) throw new Error(result.message || this.local('Role update failed'));
        const next = new Set(String(target.role || '').split(',').map(item => item.trim()).filter(Boolean));
        if (enabled) next.add(role.id); else next.delete(role.id);
        const serverRole = result.data?.role;
        target.role = typeof serverRole === 'string' ? serverRole : serverRole === null ? '' : [...next].join(',');
        this.syncRoles();
        this.statusMessage = enabled ? this.local('Granted role') : this.local('Removed role');
        this.$emit('updated');
        this.$barWarning(this.statusMessage, { status: 'correct', theme: this.theme });
      } catch (error) {
        this.syncRoles();
        this.errorMessage = error.message || this.local('Role update failed');
        this.$barWarning(this.errorMessage, { status: 'error', theme: this.theme });
      } finally { this.busy = false; this.confirming = false; }
    },
  },
};
</script>
<style scoped lang="scss">
.user-role-modal :deep(.fv-panel-control-block), .user-role-modal :deep(.fv-panel-footer) { flex-shrink: 0; }
.user-role-modal :deep(.fv-panel-main-container) { min-height: 0; }
.role-title { font-size: 20px; font-weight: 600; color: #241b38; }
.role-panel { width: 100%; min-width: 0; padding: 20px; color: #2a203d; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; }
.role-user { display: flex; align-items: center; gap: 12px; }
.role-identity { min-width: 0; overflow-wrap: anywhere; }
.role-user strong, .role-user small { display: block; }
.role-user small { margin-top: 4px; color: #90849b; }
.avatar-letter { display: grid; flex-shrink: 0; place-items: center; width: 42px; height: 42px; border-radius: 50%; background: linear-gradient(135deg,#ddb6f4,#ffb9df); color: #fff; font-weight: 800; }
.panel-caption { margin: 22px 0 12px; color: #8a7e95; font-size: 13px; line-height: 1.7; }
.role-item { display: flex; align-items: flex-start; gap: 12px; min-height: 72px; padding: 16px 0; border-top: 1px solid #eee5f5; cursor: pointer; touch-action: manipulation; }
.role-checkbox { flex-shrink: 0; width: 22px; height: 22px; margin-top: 2px; cursor: pointer; }
.role-copy { display: grid; gap: 6px; min-width: 0; overflow-wrap: anywhere; }
.role-copy strong { font-size: 15px; line-height: 1.6; }
.role-copy code { font-size: 12px; color: #a56bd1; margin-left: 6px; }
.role-copy > span { color: #8a7e95; font-size: 13px; line-height: 1.7; }
.panel-status { min-height: 22px; margin-top: 12px; color: #79658e; font-size: 13px; line-height: 1.7; }
.role-error, .role-load-error { color: #b13c60; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.role-load-error .panel-button { margin-top: 12px; }
.panel-button { min-height: 44px; border: 1px solid #e1d8ee; border-radius: 8px; padding: 10px 18px; font: inherit; font-size: 14px; background: #fff; color: #5d3679; cursor: pointer; touch-action: manipulation; }
.panel-button:disabled { opacity: .5; cursor: not-allowed; }
.panel-primary { width: 100%; color: #fff; border-color: transparent; }
.panel-button:focus-visible, .role-checkbox:focus-visible { outline: 2px solid #a56bd1; outline-offset: 3px; }
@media (max-width: 480px) { .role-panel { padding: 16px; } .role-title { font-size: 18px; } }
</style>
<style lang="scss">
/* FV mounts its global confirmation outside the panel; scope overrides to this message. */
.fv-InfoBox:has(.role-change-confirm-message) {
  padding: 12px;
  .sinfo-box-block { min-width: 0; width: 480px; max-width: 100%; max-height: calc(100dvh - 24px); }
  .title-bar, .info-box-control-block { flex-shrink: 0; }
  .info-box-content-block { min-height: 0; overflow-y: auto; }
  .role-change-confirm-message { white-space: pre-line; overflow-wrap: anywhere; line-height: 1.8; }
  .info-box-control-block .fv-button { min-height: 44px; height: auto !important; }
}
</style>
