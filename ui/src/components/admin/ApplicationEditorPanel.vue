<template>
  <Teleport to="body">
  <fv-panel class="application-editor-modal" :model-value="modelValue" theme="light" :title="editing ? '修改应用' : '添加应用'" width="min(760px, calc(100vw - 32px))" height="min(760px, calc(100dvh - 32px))" background="rgba(255,255,255,.96)" :is-central-side="true" :is-acrylic="true" :is-footer="true" @update:model-value="setVisible">
    <template #header><h2 class="panel-heading">{{ editing ? '修改应用' : '添加应用' }}</h2><fv-button theme="light" border-radius="8" :disabled="saving" aria-label="关闭应用编辑" @click="close">关闭</fv-button></template>
    <template #container>
      <form ref="editorForm" class="application-form" @submit.prevent="$emit('save')" @keydown.esc.stop.prevent="close">
        <p class="hint">回调地址必须精确匹配；只支持 HTTPS，本机开发可使用 HTTP loopback。</p>
        <label class="form-field">应用名称<input v-model.trim="form.name" :disabled="saving" required maxlength="120" autocomplete="off" /></label>
        <label class="form-field">应用说明<textarea v-model="form.description" :disabled="saving" maxlength="2000" rows="3"></textarea></label>
        <label class="form-field">客户端类型<select v-model="form.client_type" :disabled="editing || saving"><option value="public">公开客户端（SPA / 原生应用，无密钥）</option><option value="confidential">机密客户端（服务端，HTTP Basic）</option></select></label>
        <label class="form-field">回调地址（每行一个）<textarea :value="redirects" :disabled="saving" required rows="4" placeholder="https://example.com/callback" @input="$emit('update:redirects', $event.target.value)"></textarea></label>
        <label class="check-field"><input v-model="form.enabled" :disabled="saving" type="checkbox" />启用应用</label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </form>
    </template>
    <template #footer>
      <div class="panel-actions"><fv-button :disabled="saving" theme="dark" :background="gradient" border-radius="8" @click="submit">{{ saving ? '保存中…' : '保存应用' }}</fv-button><fv-button :disabled="saving" theme="light" border-radius="8" @click="close">取消</fv-button></div>
    </template>
  </fv-panel>
  </Teleport>
</template>
<script setup>
import { computed, ref } from 'vue';
import { useTheme } from '@/stores/useTheme';
const props = defineProps({ modelValue: Boolean, form: { type: Object, required: true }, editing: Boolean, saving: Boolean, redirects: { type: String, default: '' }, error: { type: String, default: '' } });
const emit = defineEmits(['update:modelValue', 'update:redirects', 'save']);
const gradient = computed(() => useTheme().gradient);
const editorForm = ref();
function reportValidity() { return editorForm.value?.reportValidity() ?? false; }
function submit() { if (!props.saving) editorForm.value?.requestSubmit(); }
// FV emits true when opening as well as false when closing.
function setVisible(value) { if (!props.saving) emit('update:modelValue', value); }
function close() { if (!props.saving) emit('update:modelValue', false); }
defineExpose({ reportValidity });
</script>
<style scoped lang="scss">
.application-editor-modal :deep(.fv-panel-control-block), .application-editor-modal :deep(.fv-panel-footer) { flex-shrink: 0; }
.application-editor-modal :deep(.fv-panel-main-container) { min-height: 0; }
.application-form { width: 100%; overflow-y: auto; overscroll-behavior: contain; display: grid; gap: 15px; padding: 20px; min-width: 0; }
.panel-heading { color: #241b38; font-size: 20px; font-weight: 600; }
.hint { color: #766d87; font-size: 13px; line-height: 1.7; }
.form-field { display: grid; gap: 7px; min-width: 0; color: #5d5570; font-size: 13px; font-weight: 700; }
.form-field input, .form-field textarea, .form-field select { box-sizing: border-box; width: 100%; min-width: 0; border: 1px solid #e1d8ee; border-radius: 10px; padding: 11px; font: inherit; font-weight: 400; background: rgba(255,255,255,.72); color: #45375d; }
.form-field textarea { resize: vertical; min-height: 80px; }
.form-field input:focus-visible, .form-field textarea:focus-visible, .form-field select:focus-visible { outline: 2px solid #a56bd1; outline-offset: 2px; }
.check-field { display: flex; align-items: center; gap: 8px; color: #5d5570; font-size: 13px; font-weight: 700; }
.check-field input { accent-color: #a56bd1; }
.panel-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.error { color: #b13c60; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
</style>
