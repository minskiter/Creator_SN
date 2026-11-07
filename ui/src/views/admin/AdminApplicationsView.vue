<template>
  <div class="applications-page">
    <div class="page-header">
      <div>
        <span class="eyebrow">CREATOR SN CONTROL ROOM</span>
        <h1>OIDC 应用管理</h1>
        <p>统一身份，安全连接。应用的创建与管理仅限管理员账户。</p>
      </div>
      <fv-button :disabled="busy" theme="dark" :background="gradient" border-radius="8" @click="edit()">添加应用</fv-button>
    </div>
    <div class="toolbar">
      <fv-text-box v-model="search" class="application-search" placeholder="搜索名称、Client ID 或回调地址" aria-label="搜索应用" icon="Filter" border-radius="8" :reveal-border="true" :is-box-shadow="true" />
      <fv-button :disabled="busy" theme="dark" :background="gradient" border-radius="8" @click="load">刷新列表</fv-button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="busy && !apps.length" class="empty-state" role="status">正在加载…</div>
    <div v-else-if="!filtered.length" class="empty-state">{{ search ? "没有匹配的应用，请尝试其他关键词。" : "尚未添加应用，点击上方按钮创建。" }}</div>
    <div v-else class="application-admin-grid" :aria-busy="busy">
      <article v-for="app in filtered" :key="app.client_id" class="application-admin-card">
        <div class="application-admin-icon" aria-hidden="true"><span class="ms-Icon ms-Icon--AppIconDefault"></span></div>
        <div class="application-admin-content">
          <div class="card-heading"><h2>{{ app.name }}</h2><span class="status" :class="{ disabled: !app.enabled }">{{ app.enabled ? "已启用" : "已停用" }}</span></div>
          <p>{{ app.description || "OIDC 应用" }}</p>
          <small>{{ app.client_type === "public" ? "公开客户端 · 无密钥" : "机密客户端 · HTTP Basic 认证" }}</small>
        </div>
        <dl class="application-details">
          <div><dt>CLIENT ID</dt><dd><code>{{ app.client_id }}</code></dd></div>
          <div><dt>回调地址</dt><dd><code v-for="uri in app.redirect_uris" :key="uri">{{ uri }}</code></dd></div>
        </dl>
        <div class="application-actions">
          <fv-button :disabled="busy" theme="light" border-radius="7" @click="edit(app)">编辑</fv-button>
          <fv-button v-if="app.client_type === 'confidential'" :disabled="busy" theme="light" border-radius="7" @click="rotate(app)">重置密钥</fv-button>
          <fv-button :disabled="busy" theme="light" border-radius="7" @click="remove(app)">删除</fv-button>
        </div>
      </article>
    </div>
    <section class="integration" aria-labelledby="integration-title">
      <div class="integration-heading"><span class="ms-Icon ms-Icon--PlugConnected" aria-hidden="true"></span><h2 id="integration-title">开发者接入</h2></div>
      <p>Discovery</p><code>https://creatorsn.com/.well-known/openid-configuration</code>
      <p class="integration-hint">授权码流程 · PKCE S256 必填 · RS256 · Scope：openid profile email · Access Token 有效期 15 分钟</p>
    </section>
    <ApplicationEditorPanel ref="editor" :model-value="editorVisible" :form="form" :editing="!!editing" :saving="busy" :redirects="redirects" :error="editorError" @update:model-value="setEditorVisible" @update:redirects="redirects = $event" @save="save" />
    <Teleport to="body">
    <fv-panel class="application-secret-modal" :model-value="secretVisible" theme="light" title="请立即保存 Client Secret" width="min(760px, calc(100vw - 32px))" height="min(360px, calc(100dvh - 32px))" background="rgba(255,255,255,.96)" :is-central-side="true" :is-acrylic="true" :is-footer="true" :show-title-bar="false">
      <template #container><div class="secret-content"><h2>请立即保存 Client Secret</h2><p>密钥仅显示这一次，关闭后无法再次查看。不要写入前端代码或提交到 Git。</p><code class="secret">{{ newSecret }}</code></div></template>
      <template #footer><fv-button :background="gradient" theme="dark" border-radius="8" @click="closeSecret">我已安全保存</fv-button></template>
    </fv-panel>
    </Teleport>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { OIDCApi } from "@/api";
import { useTheme } from "@/stores/useTheme";
import ApplicationEditorPanel from "@/components/admin/ApplicationEditorPanel.vue";
const gradient = computed(() => useTheme().gradient);
const apps = ref([]), search = ref(""), busy = ref(false), error = ref(""), editorError = ref("");
const editor = ref(), editorVisible = ref(false), secretVisible = ref(false), newSecret = ref(""), editing = ref(null), redirects = ref("");
const defaults = () => ({ name: "", description: "", client_type: "public", enabled: true });
const form = reactive(defaults());
const filtered = computed(() => apps.value.filter(app => `${app.name} ${app.client_id} ${app.redirect_uris.join(" ")}`.toLowerCase().includes(search.value.toLowerCase())));
function message(e) { const detail = e.response?.data?.detail; return typeof detail === "string" ? detail : detail ? "请检查输入格式及回调地址。" : e.message || "请求失败"; }
async function load() { if (busy.value) return; busy.value = true; error.value = ""; try { apps.value = await OIDCApi.list(); } catch (e) { error.value = message(e); } finally { busy.value = false; } }
function edit(app) { if (busy.value) return; editing.value = app?.client_id || null; Object.assign(form, app || defaults()); redirects.value = app?.redirect_uris.join("\n") || ""; editorError.value = ""; editorVisible.value = true; }
function setEditorVisible(visible) { if (!busy.value) editorVisible.value = visible; }
function showSecret(secret) { if (secret) { newSecret.value = secret; secretVisible.value = true; } }
function closeSecret() { newSecret.value = ""; secretVisible.value = false; }
async function save() {
  if (busy.value || !editor.value?.reportValidity()) return;
  busy.value = true; editorError.value = "";
  try {
    const body = { name: form.name, description: form.description, client_type: form.client_type, enabled: form.enabled, redirect_uris: redirects.value.split("\n").map(v => v.trim()).filter(Boolean) };
    const result = editing.value ? await OIDCApi.update(editing.value, body) : await OIDCApi.create(body);
    editorVisible.value = false; showSecret(result.client_secret);
  } catch (e) { editorError.value = message(e); return; } finally { busy.value = false; }
  await load();
}
async function rotate(app) {
  if (busy.value || !window.confirm(`重置「${app.name}」的密钥？旧密钥及现有授权将立即失效。`)) return;
  busy.value = true; error.value = "";
  try { showSecret((await OIDCApi.rotate(app.client_id)).client_secret); } catch (e) { error.value = message(e); } finally { busy.value = false; }
}
async function remove(app) {
  if (busy.value || !window.confirm(`删除「${app.name}」？该应用所有授权将失效。`)) return;
  busy.value = true; error.value = "";
  try { await OIDCApi.remove(app.client_id); } catch (e) { error.value = message(e); } finally { busy.value = false; }
  if (!error.value) await load();
}
onMounted(load);
</script>
<style scoped lang="scss">
.applications-page {
  position: relative;
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow: auto;
  padding: 50px clamp(22px, 5vw, 76px) 30px;
  color: #241b38;
  font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}
.page-header { display: flex; align-items: end; justify-content: space-between; gap: 20px; }
.page-header > div { min-width: 0; }
.eyebrow { font-size: 11px; letter-spacing: .2em; color: #ae65bb; font-weight: 800; }
.page-header h1 { font-size: clamp(36px, 4vw, 56px); margin: 12px 0 5px; }
.page-header p { margin: 0; color: #766d87; line-height: 1.7; }
.toolbar { display: flex; gap: 10px; margin: 28px 0; }
.application-search { width: min(430px, 100%); min-width: 0; }
.application-admin-grid { display: grid; gap: 14px; }
.application-admin-card {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid rgba(255,255,255,.95);
  border-radius: 18px;
  background: rgba(255,255,255,.72);
  box-shadow: 0 18px 50px rgba(116,77,164,.1);
}
.application-admin-icon { display: grid; width: 66px; height: 66px; place-items: center; border-radius: 17px; background: linear-gradient(145deg,#fff,#f3ecff); color: #a56bd1; font-size: 27px; }
.application-admin-content { min-width: 0; overflow-wrap: anywhere; }
.card-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.card-heading h2 { margin: 0 0 5px; font-size: 22px; }
.status { flex-shrink: 0; font-size: 12px; padding: 4px 9px; border-radius: 20px; background: #e8f4ee; color: #39755a; }
.status.disabled { color: #9c6884; background: #f6ebf0; }
.application-admin-content p { margin: 0 0 7px; color: #766d87; line-height: 1.7; white-space: pre-wrap; }
.application-admin-content small { color: #a08fae; }
.application-details { grid-column: 2 / -1; grid-row: 2; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 18px; min-width: 0; margin: 0; }
.application-details > div, .application-details dd { min-width: 0; margin: 0; }
.application-details dt { font-size: 11px; font-weight: 700; color: #8c7e99; margin-bottom: 7px; }
.application-details code, .integration code, .secret { display: block; max-width: 100%; overflow-wrap: anywhere; white-space: pre-wrap; font-size: 12px; line-height: 1.7; background: #f4effa; padding: 10px 12px; border-radius: 8px; }
.application-details code + code { margin-top: 6px; }
.application-actions { grid-column: 3; grid-row: 1; display: flex; flex-wrap: wrap; gap: 7px; }
.empty-state { padding: 90px 20px; text-align: center; color: #8c7e99; border: 1px dashed #d8c5e7; border-radius: 22px; }
.error { color: #b13c60; margin: 0 0 20px; overflow-wrap: anywhere; }
.integration { margin-top: 28px; padding: 20px; border: 1px solid rgba(255,255,255,.95); border-radius: 18px; background: rgba(255,255,255,.55); }
.integration-heading { display: flex; align-items: center; gap: 10px; color: #a56bd1; }
.integration-heading h2 { font-size: 16px; color: #45375d; }
.integration p, .secret-content p { margin: 12px 0 8px; color: #766d87; font-size: 13px; line-height: 1.7; }
.integration .integration-hint { margin-bottom: 0; }
.application-secret-modal :deep(.fv-panel-footer) { flex-shrink: 0; }
.application-secret-modal :deep(.fv-panel-main-container) { min-height: 0; }
.secret-content { width: 100%; overflow-y: auto; padding: 24px; min-width: 0; color: #241b38; }
.secret-content h2 { font-size: 22px; }
.secret { margin-top: 20px; user-select: all; }
@media (max-width: 1100px) {
  .application-admin-card { grid-template-columns: 72px minmax(0, 1fr); }
  .application-details { grid-template-columns: minmax(0, 1fr); }
  .application-actions { grid-column: 2; grid-row: 3; }
}
@media (max-width: 720px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .toolbar { align-items: stretch; flex-direction: column; }
  .application-search { width: 100%; }
  .application-admin-card { grid-template-columns: 58px minmax(0, 1fr); padding: 18px 16px; }
  .application-admin-icon { width: 56px; height: 56px; }
  .application-details { grid-column: 1 / -1; }
  .application-actions { grid-column: 1 / -1; }
}
</style>
