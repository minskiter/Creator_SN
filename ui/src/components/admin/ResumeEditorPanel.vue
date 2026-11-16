<template>
	<Teleport to="body">
	<fv-panel
		class="resume-editor-modal"
		v-model="visible"
		theme="light"
		:title="editing ? local('Edit resume') : local('Add resume')"
		width="min(900px, calc(100vw - 32px))"
		height="min(780px, calc(100dvh - 24px))"
		background="rgba(255,255,255,.96)"
		:is-central-side="true"
		:is-acrylic="true"
		:is-footer="true"
	>
		<template #header>
			<h2 class="panel-title">{{ editing ? local("Edit resume") : local("Add resume") }}</h2>
			<button type="button" class="panel-button" :disabled="saving" @click="visible = false">{{ local("Close") }}</button>
		</template>
		<template #container
			><div
				class="editor-panel"
				@paste.capture="handlePowerEditorPaste"
				@drop.capture="handlePowerEditorDrop"
			>
				<label class="mobile-user-label">{{ local("Bind user") }}
					<select class="mobile-user-picker" :value="form.userid || ''" :disabled="saving" @change="chooseNativeUser($event.target.value)">
						<option v-if="!userOptions.some(option => option.value === (form.userid || ''))" :value="form.userid || ''">{{ form.userid || local("Unbound resume") }}</option>
						<option v-for="option in userOptions" :key="option.key" :value="option.value">{{ option.text }}</option>
					</select>
				</label>
				<span class="bind-user-label desktop-user-label"
					>{{ local("Bind user")
					}}<fv-combobox
						v-model="selectedUser"
						class="user-picker"
						theme="light"
						:options="userOptions"
						:disabled="saving"
						:placeholder="local('Unbound resume')"
						background="rgba(255,255,255,.72)"
						border-color="rgba(241, 222, 252, 0.3)"
						choosenSliderBackground="rgba(163, 121, 225, 1)"
						:reveal-border="true"
						:is-box-shadow="true"
						style="z-index: 9"
						@choose-item="$emit('choose-user', $event)" /></span
				><power-editor
					ref="editor"
					class="resume-rich-editor"
					:model-value="editorValue(form.introduction)"
					:img-interceptor="imgInterceptor"
					editor-background="transparent"
					editor-out-side-background="transparent"
					@save-json="$emit('save-content', $event)"
					style="width: 100%"
				></power-editor>
				<p class="hint">
					{{
						local(
							"Basic information comes from the bound user's profile.",
						)
					}}
				</p>
			</div></template
		>
		<template #footer
			><div class="resume-editor-actions"><fv-button
				theme="dark"
				:background="gradient"
				border-radius="8"
				:disabled="saving"
				style="width: 120px"
				@click="$emit('save')"
				>{{
					saving ? local("Saving…") : local("Save resume")
				}}</fv-button
			>
			<fv-button
				:theme="theme"
				border-radius="8"
				:disabled="saving"
				style="width: 120px; margin-left: 5px"
				@click="visible = false"
				>{{ local("Cancel") }}</fv-button
			>
			</div>
		</template>
	</fv-panel>
	</Teleport>
</template>
<script>
import { useAppStore } from "@/store";
import {
	handlePowerEditorImageDrop,
	handlePowerEditorImagePaste,
} from "@/utils/powerEditorImageInterceptor";

export default {
	name: "ResumeEditorPanel",
	props: {
		modelValue: { type: Boolean, default: false },
		editing: { type: Boolean, default: false },
		saving: { type: Boolean, default: false },
		theme: { type: String, default: "light" },
		gradient: { type: String, default: "" },
		form: { type: Object, required: true },
		userOption: { type: Object, required: true },
		userOptions: { type: Array, default: () => [] },
		imgInterceptor: { type: Function, default: null },
	},
	emits: [
		"update:modelValue",
		"update:userOption",
		"choose-user",
		"save-content",
		"save",
	],
	computed: {
		visible: {
			get() {
				return this.modelValue;
			},
			set(value) {
				if (!this.saving) this.$emit("update:modelValue", value);
			},
		},
		selectedUser: {
			get() {
				return this.userOption;
			},
			set(value) {
				this.$emit("update:userOption", value);
			},
		},
	},
	methods: {
		chooseNativeUser(userid) {
			if (this.saving) return;
			const option = this.userOptions.find(option => option.value === userid);
			if (option) {
				this.selectedUser = option;
				this.$emit("choose-user", option);
			}
		},
		handlePowerEditorPaste(event) {
			return handlePowerEditorImagePaste(
				event,
				() => this.$refs.editor,
				() => this.$emit("image-error"),
			);
		},
		handlePowerEditorDrop(event) {
			return handlePowerEditorImageDrop(
				event,
				() => this.$refs.editor,
				() => this.$emit("image-error"),
			);
		},
		local(text, params) {
			return useAppStore().local(text, params);
		},
		editorValue(content) {
			if (!content) return { type: "doc", content: [] };
			if (typeof content !== "string") return content;
			try {
				return JSON.parse(content);
			} catch (_) {
				return content;
			}
		},
	},
};
</script>
<style scoped lang="scss">
.resume-editor-modal :deep(.fv-panel-control-block), .resume-editor-modal :deep(.fv-panel-footer) { flex-shrink: 0; }
.resume-editor-modal :deep(.fv-panel-main-container) { min-height: 0; }
.panel-title { min-width: 0; color: #241b38; font-size: 20px; overflow-wrap: anywhere; }
.panel-button { flex-shrink: 0; min-height: 44px; border: 1px solid #e1d8ee; border-radius: 8px; padding: 8px 16px; background: #fff; color: #5d3679; font: inherit; cursor: pointer; }
.panel-button:disabled { opacity: .5; cursor: not-allowed; }
.resume-editor-actions { display: flex; gap: 8px; width: 100%; }
.resume-editor-actions > .fv-Button { min-height: 44px; }
.mobile-user-label { display: none; }
.editor-panel {
	width: 100%;
	min-width: 0;
	min-height: 0;
	overflow-y: auto;
	overscroll-behavior: contain;
	display: flex;
	flex-direction: column;
	gap: 16px;
	padding: 20px;
}
.editor-panel .bind-user-label {
	display: grid;
	gap: 7px;
	color: #5d5570;
	font-size: 13px;
	font-weight: 700;
}
.editor-panel .user-picker {
	width: 100%;
}
.editor-panel .resume-rich-editor {
	width: 100%;
	min-width: 0;
	max-width: 100%;
	min-height: 320px;
	height: 420px;
	flex-shrink: 0;
}
.hint {
	margin: 0;
	color: #978ba3;
	font-size: 12px;
	line-height: 1.7;
	overflow-wrap: anywhere;
}
@media (max-width: 600px) {
	.editor-panel { padding: 14px; gap: 12px; }
	.editor-panel .desktop-user-label { display: none; }
	.mobile-user-label { display: grid; gap: 8px; color: #5d5570; font-size: 13px; font-weight: 700; }
	.mobile-user-picker { width: 100%; min-width: 0; min-height: 44px; padding: 10px; border: 1px solid #e1d8ee; border-radius: 8px; background: #fff; color: #45375d; font: inherit; font-size: 16px; }
	.editor-panel .resume-rich-editor { min-height: 240px; height: 50dvh; }
	.resume-editor-actions > .fv-Button { flex: 1; width: auto !important; margin-left: 0 !important; }
	.editor-panel :deep(.tip-tap-editor) { padding-left: 10px; padding-right: 10px; overflow-wrap: anywhere; }
}
</style>
