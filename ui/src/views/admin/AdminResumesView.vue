<template>
	<div class="resumes-page">
		<div class="page-header">
			<div>
				<span class="eyebrow">CREATOR SN CONTROL ROOM</span>
				<h1>{{ local("Resume Management") }}</h1>
				<p>{{ local("Create, edit, and bind member resumes.") }}</p>
			</div>
			<fv-button
				theme="dark"
				:background="gradient"
				border-radius="8"
				style="width: 120px"
				:disabled="saving"
				@click="openCreate"
				>{{ local("Add resume") }}</fv-button
			>
		</div>
		<div class="resume-toolbar">
			<span>{{ local("Resume count: {total}", { total: resumes.length }) }}</span>
			<button type="button" class="touch-button" :disabled="loading || saving" @click="load">{{ loading ? local("Loading…") : local("Refresh list") }}</button>
		</div>
		<p v-if="loadError" class="load-error" role="alert">{{ loadError }}</p>
		<section class="mobile-resumes" :aria-label="local('Resume Management')" :aria-busy="loading">
			<p v-if="loading && !resumes.length" class="mobile-empty" role="status">{{ local("Loading…") }}</p>
			<p v-else-if="!resumes.length && !loadError" class="mobile-empty">{{ local("No resumes found") }}</p>
			<article v-for="item in resumes" :key="item.id" class="mobile-resume-card">
				<h2>{{ item.user?.name || item.userid || local("Unbound resume") }}</h2>
				<dl>
					<div><dt>{{ local("Bound user") }}</dt><dd>{{ item.userid || local("Unbound") }}</dd></div>
					<div><dt>{{ local("Email") }}</dt><dd>{{ item.user?.email || "—" }}</dd></div>
					<div><dt>{{ local("Updated") }}</dt><dd>{{ formatDate(item.updated_at) }}</dd></div>
				</dl>
				<div class="mobile-resume-actions">
					<button type="button" class="touch-button edit-button" :style="{ background: gradient }" :disabled="saving" @click="openEdit(item)">{{ local("Edit") }}</button>
					<button type="button" class="touch-button delete-button" :disabled="saving || loading" @click="remove(item)">{{ local("Delete") }}</button>
				</div>
			</article>
		</section>
		<div class="list-card">
			<fv-details-list
				v-model="resumes"
				:theme="theme"
				:head="localizedHead"
				:foreground="color"
				style="width: 100%; height: 100%"
				><template #column_0="x"
					><span>{{
						x.item.user?.name ||
						x.item.userid ||
						local("Unbound resume")
					}}</span></template
				><template #column_1="x"
					><span class="muted">{{
						x.item.userid || local("Unbound")
					}}</span></template
				><template #column_2="x"
					><span class="muted">{{
						x.item.user?.email || "—"
					}}</span></template
				><template #column_3="x"
					><span class="muted">{{
						formatDate(x.item.updated_at)
					}}</span></template
				><template #column_4="x"
					><div class="actions">
						<fv-button
							icon="Edit"
							theme="dark"
							:background="gradient"
							border-radius="6"
							@click="openEdit(x.item)"
							>{{ local("Edit") }}</fv-button
						><fv-button
							icon="Delete"
							theme="dark"
							background="rgba(200, 38, 45, 1)"
							border-radius="6"
							@click="remove(x.item)"
							>{{ local("Delete") }}</fv-button
						>
					</div></template
				></fv-details-list
			>
		</div>
		<ResumeEditorPanel
			v-model="visible"
			:editing="editing"
			:saving="saving"
			:theme="theme"
			:gradient="gradient"
			:form="form"
			:user-option="userOption"
			:user-options="userOptions"
			:img-interceptor="resumeImageInterceptor"
			@update:user-option="userOption = $event"
			@choose-user="selectUser"
			@save-content="saveContent"
			@save="save"
		/>
	</div>
</template>
<script>
import { ResumeApi, UserApi } from "@/api";
import ResumeEditorPanel from "@/components/admin/ResumeEditorPanel.vue";
import { useAppStore } from "@/store";
import { mapState } from "pinia";
import { useTheme } from "@/stores/useTheme";
import { createResumeImageInterceptor } from "@/utils/powerEditorImageInterceptor";
export default {
	name: "AdminResumesView",
	components: { ResumeEditorPanel },
	data() {
		return {
			resumes: [],
			users: [],
			visible: false,
			editing: false,
			saving: false,
			loading: false,
			loadError: "",
			form: {
				id: null,
				userid: "",
				introduction: { type: "doc", content: [] },
			},
			userOption: { key: "", value: "", text: "" },
			userOptions: [],
			head: [
				{ content: "Member", width: 230 },
				{ content: "Bound user", width: 220 },
				{ content: "Email", width: 250 },
				{ content: "Updated", width: 190 },
				{ content: "Actions", width: 170 },
			],
		};
	},
	mounted() {
		this.load();
		this.loadUsers();
	},
	computed: {
		...mapState(useTheme, ["theme", "color", "gradient"]),
		localizedHead() {
			return this.head.map((item) => ({
				...item,
				content: this.local(item.content),
			}));
		},
	},
	methods: {
		local(text, params) {
			return useAppStore().local(text, params);
		},
		async load() {
			if (this.loading) return;
			this.loading = true;
			this.loadError = "";
			try {
				const result = await ResumeApi.list();
				if (result.code !== 200) throw new Error(result.message || this.local("Failed to load resumes"));
				this.resumes = result.data || [];
			} catch (error) {
				this.loadError = error.message || this.local("Failed to load resumes");
			} finally { this.loading = false; }
		},
		async loadUsers() {
			try {
				const result = await UserApi.list(undefined, 0, 9999);
				if (result.code !== 200) throw new Error(result.message || this.local("Failed to load users"));
				this.users = result.data || [];
				this.rebuildUserOptions();
				this.userOption = this.findUserOption(this.form.userid);
			} catch (error) {
				this.$barWarning(error.message || this.local("Failed to load users"), { status: "error", theme: this.theme });
			}
		},
		rebuildUserOptions() {
			this.userOptions = [
				{ key: "", value: "", text: this.local("Unbound resume") },
				...this.users.map((user) => ({
					key: user.userid,
					value: user.userid,
					text: `${user.name || user.userid} · ${user.userid}`,
				})),
			];
		},
		openCreate() {
			if (this.saving) return;
			this.editing = false;
			this.form = {
				id: null,
				userid: "",
				introduction: { type: "doc", content: [] },
			};
			this.userOption = this.findUserOption("");
			this.visible = true;
		},
		openEdit(item) {
			if (this.saving) return;
			this.editing = true;
			this.form = {
				id: item.id,
				userid: item.userid || "",
				introduction: item.introduction || { type: "doc", content: [] },
			};
			this.userOption = this.findUserOption(this.form.userid);
			this.visible = true;
		},
		findUserOption(userid) {
			return (
				this.userOptions.find((option) => option.value === userid) ||
				{ key: userid || "", value: userid || "", text: userid || this.local("Unbound resume") }
			);
		},
		selectUser(option) {
			this.userOption = option;
			this.form.userid = option?.value || "";
		},
		normalizeContent(content) {
			if (!content) return { type: "doc", content: [] };
			if (typeof content !== "string") return content;
			try {
				return JSON.parse(content);
			} catch (_) {
				return content;
			}
		},
		editorValue(content) {
			return this.normalizeContent(content);
		},
		resumeImageInterceptor(payload) {
			return createResumeImageInterceptor({
				getResumeId: () => this.form.id,
				local: this.local,
			})(payload);
		},
		saveContent(content) {
			this.form.introduction = content;
		},
		async save() {
			if (this.saving) return;
			this.saving = true;
			try {
				const result = await ResumeApi.save(this.form);
				if (result.code === 200) {
					this.visible = false;
					await this.load();
					this.$barWarning(this.local("Resume saved"), {
						status: "correct",
						theme: this.theme,
					});
				} else
					this.$barWarning(
						result.message || this.local("Save failed"),
						{ status: "error", theme: this.theme },
					);
			} catch (error) {
				this.$barWarning(error.message || this.local("Save failed"), { status: "error", theme: this.theme });
			} finally {
				this.saving = false;
			}
		},
		async remove(item) {
			if (this.saving || this.loading) return;
			this.$infoBox(this.local("Delete this resume?"), {
				theme: this.theme,
				status: "error",
				confirmTitle: this.local("Confirm"),
				cancelTitle: this.local("Cancel"),
				confirm: async () => {
					if (this.saving || this.loading) return;
					this.saving = true;
					try {
						const result = await ResumeApi.remove(item.id);
						if (result.code !== 200) throw new Error(result.message || this.local("Delete failed"));
						await this.load();
					} catch (error) {
						this.$barWarning(error.message || this.local("Delete failed"), { status: "error", theme: this.theme });
					} finally { this.saving = false; }
				},
			});
		},
		formatDate(value) {
			return value
				? new Date(value).toLocaleString("zh-CN", {
						dateStyle: "short",
						timeStyle: "short",
					})
				: "—";
		},
	},
};
</script>
<style scoped lang="scss">
.resumes-page {
	position: relative;
	flex: 1;
	min-width: 0;
	height: 100%;
	overflow: auto;
	padding: 50px clamp(22px, 5vw, 76px) 30px;
	color: #241b38;
	font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}
.page-header {
	display: flex;
	align-items: end;
	justify-content: space-between;
	gap: 20px;
}
.page-header > div { min-width: 0; overflow-wrap: anywhere; }
.page-header > .fv-Button { flex-shrink: 0; min-height: 44px; }
.resume-toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; margin: 24px 0 14px; color: #8f839a; font-size: 13px; }
.load-error { color: #b13c60; overflow-wrap: anywhere; line-height: 1.7; margin: 12px 0; }
.mobile-resumes { display: none; }
.touch-button { min-height: 44px; border: 1px solid #e1d8ee; border-radius: 8px; padding: 10px 16px; background: #fff; color: #5d3679; font: inherit; font-size: 14px; cursor: pointer; touch-action: manipulation; }
.touch-button:disabled { opacity: .5; cursor: not-allowed; }
.touch-button:focus-visible { outline: 2px solid #a56bd1; outline-offset: 3px; }
.eyebrow {
	font-size: 11px;
	letter-spacing: 0.2em;
	color: #ae65bb;
	font-weight: 800;
}
.page-header h1 {
	font-size: clamp(36px, 4vw, 56px);
	margin: 12px 0 5px;
}
.page-header p {
	margin: 0;
	color: #766d87;
}
.list-card {
	height: calc(100% - 260px);
	min-height: 340px;
	margin-top: 14px;
	overflow: hidden;
	border: 1px solid rgba(255, 255, 255, 0.95);
	border-radius: 18px;
	background: rgba(255, 255, 255, 0.72);
	box-shadow: 0 20px 55px rgba(116, 77, 164, 0.11);
}
.actions {
	display: flex;
	gap: 7px;
}
.muted {
	color: #8f839a;
}
@media (max-width: 1024px) {
	.list-card { display: none; }
	.mobile-resumes { display: grid; gap: 14px; }
	.mobile-empty { padding: 36px 16px; color: #8f839a; text-align: center; }
	.mobile-resume-card { min-width: 0; padding: 18px; border: 1px solid #fff; border-radius: 16px; background: rgba(255,255,255,.78); box-shadow: 0 12px 30px rgba(116,77,164,.08); }
	.mobile-resume-card h2 { margin: 0 0 16px; font-size: 19px; overflow-wrap: anywhere; }
	.mobile-resume-card dl { display: grid; gap: 12px; }
	.mobile-resume-card dl > div { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 12px; }
	.mobile-resume-card dt { color: #8f839a; font-size: 13px; }
	.mobile-resume-card dd { margin: 0; min-width: 0; color: #45375d; font-size: 14px; overflow-wrap: anywhere; }
	.mobile-resume-actions { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; margin-top: 18px; }
	.edit-button { color: #fff; border-color: transparent; }
	.delete-button { color: #b13c60; border-color: #eed4df; }
}
@media (max-width: 600px) {
	.resumes-page { padding: 28px 16px 24px; }
	.page-header { align-items: flex-start; flex-direction: column; gap: 16px; }
	.page-header h1 { font-size: 32px; }
	.page-header p { line-height: 1.7; }
}
@media (max-width: 360px) {
	.mobile-resume-card dl > div { grid-template-columns: minmax(0, 1fr); gap: 5px; }
}
</style>
