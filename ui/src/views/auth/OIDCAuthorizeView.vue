<template>
  <main class="consent-page">
    <section class="consent-card">
      <span class="eyebrow">CREATOR SN IDENTITY</span>
      <h1>应用授权</h1>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-else-if="!application">正在验证应用…</p>
      <template v-else>
        <h2>{{ application.name }}</h2><p>{{ application.description }}</p>
        <p>该应用请求使用你的 Creator SN 账户：</p>
        <ul><li v-for="scope in application.scopes" :key="scope">{{ labels[scope] || scope }}</li></ul>
        <p class="account">当前账户：{{ user.info.userid }}</p>
        <small>授权后将返回已登记的地址：</small><code>{{ application.redirect_uri }}</code>
        <p class="hint">仅授权你信任的应用。你的密码不会提供给此应用，邮箱如未验证将明确标记。</p>
        <div class="actions"><fv-button :disabled="busy" border-radius="8" @click="decide('deny')">拒绝</fv-button><fv-button :disabled="busy" theme="dark" :background="gradient" border-radius="8" @click="decide('allow')">{{ busy ? "处理中…" : "同意并继续" }}</fv-button></div>
      </template>
      <router-link to="/home">返回首页</router-link>
    </section>
  </main>
</template>
<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { OIDCApi } from "@/api";
import { useUserStore } from "@/stores/useUser";
import { useTheme } from "@/stores/useTheme";
const route = useRoute(), router = useRouter(), user = useUserStore();
const gradient = computed(() => useTheme().gradient);
const application = ref(null), error = ref(""), busy = ref(false);
const labels = { openid: "识别你的账户（唯一标识）", profile: "读取显示名称和用户名", email: "读取邮箱地址及验证状态" };
let request;
function handleError(e) {
  if (e.response?.status === 401) {
    user.logout();
    router.replace({ path: "/login", query: { return_url: route.fullPath } });
    return;
  }
  error.value = typeof e.response?.data?.detail === "string" ? e.response.data.detail : "应用授权请求无效，请从原应用重新发起。";
}
onMounted(async () => {
  const allowed = ["client_id", "redirect_uri", "response_type", "scope", "state", "nonce", "code_challenge", "code_challenge_method"];
  if (Object.entries(route.query).some(([key, value]) => !allowed.includes(key) || typeof value !== "string")) {
    error.value = "应用授权参数无效。"; return;
  }
  request = Object.freeze({ ...route.query });
  try { application.value = await OIDCApi.preview(request); } catch (e) { handleError(e); }
});
async function decide(decision) {
  if (busy.value) return;
  busy.value = true;
  try { const result = await OIDCApi.authorize({ ...request, decision }); window.location.assign(result.redirect_to); } catch (e) { handleError(e); busy.value = false; }
}
</script>
<style scoped>
.consent-page{min-height:100vh;display:grid;place-items:center;padding:28px;background:linear-gradient(145deg,#fbf9ff,#f0ebff 52%,#eaf9ff);box-sizing:border-box;color:#45375d}.consent-card{box-sizing:border-box;width:min(100%,520px);background:#ffffffcf;border:1px solid #e7def1;border-radius:24px;padding:36px;box-shadow:0 24px 80px #7454931a}.eyebrow{font-size:11px;letter-spacing:.18em;color:#a56bd1}h1{font-size:28px}h2{font-size:20px}p,li{line-height:1.8;color:#796d8b}code{display:block;overflow-wrap:anywhere;background:#f3edf9;border-radius:8px;padding:12px;margin-top:8px}.actions{display:flex;justify-content:flex-end;gap:12px;margin:24px 0}a{font-size:13px;color:#9568bd}.error{color:#b13c60}.hint,small{font-size:12px}.account{font-weight:700}@media(max-width:520px){.consent-card{padding:24px}}
</style>
