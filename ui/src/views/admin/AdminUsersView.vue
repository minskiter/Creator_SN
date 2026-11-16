<template>
	<div class="users-page">
		<div class="page-header">
			<div>
				<span class="eyebrow">CREATOR SN CONTROL ROOM</span>
				<h1>{{ local("User Management") }}</h1>
				<p>{{ local("Manage invited members, permissions, and account security.") }}</p>
			</div>
			<div class="header-stat">
				<strong>{{ total }}</strong
				><span>{{ local("users") }}</span>
			</div>
		</div>
		<div class="toolbar">
			<fv-text-box
				v-model="currentSearch"
				class="user-search"
				:placeholder="local('Search account or email')"
				icon="Filter"
				border-radius="6"
				:reveal-border="true"
				:is-box-shadow="true"
				@keyup="handleSearchKeyup"
			></fv-text-box
			><fv-button
				:background="gradient"
				theme="dark"
				border-radius="8"
				:is-box-shadow="true"
				:disabled="loading"
				@click="getUsers"
				>{{ loading ? local("Loading…") : local("Refresh list") }}</fv-button
			>
		</div>
		<p v-if="loadError" class="load-error" role="alert">{{ loadError }}</p>
		<section class="mobile-users" :aria-label="local('User Management')" :aria-busy="loading">
			<p v-if="loading && !users.length" class="mobile-empty" role="status">{{ local("Loading…") }}</p>
			<p v-else-if="!users.length && !loadError" class="mobile-empty">{{ local("No users found") }}</p>
			<article v-for="item in users" :key="item.userid" class="mobile-user-card">
				<button type="button" class="user-link mobile-user-heading" :aria-label="local('Manage permissions') + ' · ' + item.userid" @click="showUserRole(item)">
					<span class="avatar-letter">{{ firstLetter(item) }}</span>
					<span class="mobile-user-identity"><strong>{{ item.userid }}</strong><small>{{ formatDate(item.last_login) }}</small></span>
				</button>
				<dl class="mobile-user-details">
					<div><dt>{{ local("Name") }}</dt><dd>{{ item.name || "—" }}</dd></div>
					<div><dt>{{ local("Email") }}</dt><dd>{{ item.email || "—" }}</dd></div>
					<div><dt>{{ local("Phone") }}</dt><dd>{{ item.phone || "—" }}</dd></div>
					<div><dt>{{ local("Gender") }}</dt><dd>{{ item.gender || "—" }}</dd></div>
					<div><dt>{{ local("Invite code") }}</dt><dd>{{ item.invite_code || "—" }}</dd></div>
					<div class="mobile-user-roles"><dt>{{ local("User roles") }}</dt><dd><span v-for="role in roleNames(item.role)" :key="role" class="role-chip" :class="{ 'role-admin': role === 'admin' }">{{ roleLabel(role) }} <code>{{ role }}</code></span><span v-if="!roleNames(item.role).length">{{ local("No roles assigned") }}</span></dd></div>
				</dl>
				<div class="mobile-user-actions">
					<button type="button" class="touch-button permission-button" :style="{ background: gradient }" :disabled="loading" @click="showUserRole(item)">{{ local("Manage permissions") }}</button>
					<button type="button" class="touch-button" :disabled="loading" @click="resetPassword(item)">{{ local("Reset password") }}</button>
				</div>
			</article>
		</section>
		<div class="list-card">
			<fv-details-list
				v-model="users"
				:theme="theme"
				:head="localizedHead"
				:filter="currentSearch"
				:foreground="color"
				style="width: 100%; height: 100%"
				:multi-selection="false"
				@rightclick="currentItem = $event"
				><template #column_0="x"
					><span class="index-cell">{{
						x.row_index + 1 + (page - 1) * pageSize
					}}</span></template
				><template #column_1="x"
					><button class="user-link" @click="showUserRole(x.item)">
						<span class="avatar-letter">{{
							firstLetter(x.item)
						}}</span
						><span
							><strong>{{ x.item.userid }}</strong
							><small>{{
								formatDate(x.item.last_login)
							}}</small></span
						>
					</button></template
				><template #column_2="x"
					><span>{{ x.item.name || "—" }}</span></template
				><template #column_3="x"
					><fv-tag
						:theme="theme"
						:model-value="
							x.item.gender ? [{ text: x.item.gender }] : []
						"
					></fv-tag></template
				><template #column_4="x"
					><span class="muted-text">{{
						x.item.email || "—"
					}}</span></template
				><template #column_5="x"
					><fv-tag
						:theme="theme"
						:model-value="
							x.item.invite_code
								? [
										{
											text: x.item.invite_code,
											type: 'warning',
										},
									]
								: []
						"
					></fv-tag></template
				><template #column_6="x"
					><span class="muted-text">{{
						x.item.phone || "—"
					}}</span></template
				><template #column_7="x"
					><div class="role-actions">
						<fv-tag
							:theme="theme"
							:model-value="roleTags(x.item.role)"
							@click="showUserRole(x.item)"
						></fv-tag
						><fv-button
							theme="light"
							border-radius="6"
							style="flex-shrink: 0"
							@click="showUserRole(x.item)"
							>{{ local("Permission") }}</fv-button
						><fv-button
							theme="light"
							border-radius="6"
							style="flex-shrink: 0"
							@click="resetPassword(x.item)"
							>{{ local("Reset password") }}</fv-button
						>
					</div></template
				><template #menu
					><div class="right-menu">
						<span @click="showUserRole(currentItem)"
							><i class="ms-Icon ms-Icon--Permissions"></i>
							<p>{{ local("Manage permissions") }}</p></span
						><span @click="resetPassword(currentItem)"
							><i class="ms-Icon ms-Icon--Lock"></i>
							<p>{{ local("Reset password") }}</p></span
						>
					</div></template
				></fv-details-list
			>
		</div>
		<div class="bottom-bar">
			<span
				>{{ local("Page {page} · {size} per page, {total} users", { page, size: pageSize, total }) }}</span
			><fv-pagination
				class="desktop-pagination"
				:model-value="page"
				:theme="theme"
				:total="totalPages"
				:foreground="color"
				background="rgba(255,255,255,.72)"
				:shadow="true"
				border-radius="7"
				@update:model-value="handlePageChange"
			></fv-pagination>
			<nav class="mobile-pagination" :aria-label="local('User pagination')">
				<button type="button" class="touch-button" :disabled="loading || page <= 1" @click="handlePageChange(page - 1)">{{ local("Previous page") }}</button>
				<span aria-live="polite">{{ page }} / {{ totalPages }}</span>
				<button type="button" class="touch-button" :disabled="loading || page >= totalPages" @click="handlePageChange(page + 1)">{{ local("Next page") }}</button>
			</nav>
		</div>
		<user-role-panel
			v-model="showRolePanel"
			:user="currentItem"
			:roles="roles"
			:loading="rolesLoading"
			:error="rolesError"
			@updated="getUsers"
			@retry="getRoles"
		></user-role-panel>
	</div>
</template>
<script>
import { UserApi } from "@/api";
import UserRolePanel from "@/components/admin/UserRolePanel.vue";
import { useAppStore } from "@/store";
import { mapState } from "pinia";
import { useTheme } from "@/stores/useTheme";
export default {
	name: "AdminUsersView",
	components: { UserRolePanel },
	data() {
		return {
			users: [],
			roles: [],
			currentSearch: "",
			currentItem: {},
			showRolePanel: false,
			page: 1,
			pageSize: 10,
			total: 0,
			loading: false,
			loadError: "",
			rolesLoading: false,
			rolesError: "",
			usersRequest: 0,
			head: [
				{ content: "No.", width: 70 },
				{ content: "Account", sortName: "userid", width: 220 },
				{ content: "Name", sortName: "name", width: 140 },
				{ content: "Gender", sortName: "gender", width: 100 },
				{ content: "Email", sortName: "email", width: 240 },
				{ content: "Invite code", sortName: "invite_code", width: 150 },
				{ content: "Phone", sortName: "phone", width: 170 },
				{ content: "Role / Actions", sortName: "role", width: 340 },
			],
		};
	},
	mounted() {
		this.getUsers();
		this.getRoles();
	},
	computed: {
		...mapState(useTheme, ["theme", "color", "gradient"]),
		localizedHead() {
			return this.head.map((item) => ({ ...item, content: this.local(item.content) }));
		},
		totalPages() {
			return Math.max(1, Math.ceil(this.total / this.pageSize));
		},
	},
	methods: {
		local(text, params) {
			return useAppStore().local(text, params);
		},
		async getUsers() {
			const request = ++this.usersRequest;
			this.loading = true;
			this.loadError = "";
			try {
				const [list, count] = await Promise.all([
					UserApi.list(
						this.currentSearch || undefined,
						(this.page - 1) * this.pageSize,
						this.pageSize,
					),
					UserApi.count(this.currentSearch || undefined),
				]);
				if (request !== this.usersRequest) return;
				if (list.code !== 200 || count.code !== 200)
					throw new Error(list.message || count.message || this.local("Failed to load users"));
				this.users = list.data || [];
				this.total = Number(count.data || 0);
				if (this.showRolePanel) this.currentItem = this.users.find(item => item.userid === this.currentItem.userid) || this.currentItem;
			} catch (error) {
				if (request === this.usersRequest) this.loadError = error.message || this.local("Failed to load users");
			} finally {
				if (request === this.usersRequest) this.loading = false;
			}
		},
		async getRoles() {
			if (this.rolesLoading) return;
			this.rolesLoading = true;
			this.rolesError = "";
			try {
				const result = await UserApi.roles();
				if (result.code !== 200) throw new Error(result.message || this.local("Failed to load roles"));
				this.roles = result.data || [];
			} catch (error) {
				this.roles = [];
				this.rolesError = error.message || this.local("Failed to load roles");
			} finally {
				this.rolesLoading = false;
			}
		},
		handleSearchKeyup(event) {
			if (event.key === "Enter") {
				this.page = 1;
				this.getUsers();
			}
		},
		handlePageChange(page) {
			if (this.loading || page < 1 || page > this.totalPages) return;
			this.page = page;
			this.getUsers();
		},
		showUserRole(item) {
			if (!item?.userid) return;
			this.currentItem = item;
			this.showRolePanel = true;
		},
		roleTags(role) {
			return this.roleNames(role).map((text) => ({
				text,
				type: text === "admin" ? "warning" : "correct",
			}));
		},
		roleNames(role) {
			return String(role || "")
				.split(",")
				.map(value => value.trim())
				.filter(Boolean);
		},
		roleLabel(role) {
			return role === "admin" ? this.local("Administrator") : role === "user" ? this.local("Regular user") : role;
		},
		firstLetter(item) {
			return (item.name || item.userid || "?").slice(0, 1).toUpperCase();
		},
		formatDate(value) {
			if (!value) return this.local("Never logged in");
			const date = new Date(value);
			return Number.isNaN(date.getTime())
				? value
				: date.toLocaleString("zh-CN", {
						dateStyle: "short",
						timeStyle: "short",
					});
		},
		resetPassword(item) {
			if (!item.userid) return;
			this.$infoBox(this.local("Reset password for {userid} to the account name?", { userid: item.userid }), {
				status: "error",
				theme: this.theme,
				confirmTitle: this.local("Confirm"),
				cancelTitle: this.local("Cancel"),
				confirm: async () => {
					try {
						const result = await UserApi.resetPassword(item.userid);
						if (result.code !== 200)
							throw new Error(result.message || this.local("Reset password"));
						this.$barWarning(
							this.local("Password reset. Temporary password: {userid}", { userid: item.userid }),
							{ status: "correct", theme: this.theme },
						);
					} catch (error) {
						this.$barWarning(error.message || this.local("Reset password"), {
							status: "error",
							theme: this.theme,
						});
					}
				},
			});
		},
	},
};
</script>
<style scoped lang="scss">
.users-page {
	position: relative;
	flex: 1;
	min-width: 0;
	height: 100%;
	overflow: auto;
	padding: 50px clamp(22px, 5vw, 76px) 30px;
	color: #241b38;
	font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}
.page-header,
.toolbar,
.bottom-bar {
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 20px;
}
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
.header-stat {
	display: grid;
	justify-items: end;
	color: #847594;
}
.header-stat strong {
	font-size: 34px;
	color: #9d66c8;
}
.toolbar {
	align-items: center;
	margin: 32px 0 14px;
}
.user-search {
	width: min(430px, 100%);
	min-width: 0;
}
.list-card {
	height: calc(100% - 260px);
	min-height: 340px;
	overflow: hidden;
	border: 1px solid rgba(255, 255, 255, 0.95);
	border-radius: 18px;
	background: rgba(255, 255, 255, 0.72);
	box-shadow: 0 20px 55px rgba(116, 77, 164, 0.11);
}
.user-link {
	display: flex;
	align-items: center;
	gap: 9px;
	border: 0;
	background: transparent;
	color: inherit;
	text-align: left;
	cursor: pointer;
	font: inherit;
	min-height: 44px;
	min-width: 0;
}
.avatar-letter {
	display: grid;
	place-items: center;
	width: 32px;
	height: 32px;
	border-radius: 50%;
	background: linear-gradient(135deg, #ddb6f4, #ffb9df);
	color: #fff;
	font-size: 12px;
	font-weight: 800;
	flex-shrink: 0;
}
.user-link strong,
.user-link small {
	display: block;
}
.user-link small {
	margin-top: 3px;
	color: #968ba1;
	font-size: 10px;
}
.index-cell,
.muted-text {
	color: #8f839a;
}
.role-actions {
	display: flex;
	align-items: center;
	gap: 7px;
	overflow-x: auto;
}
.role-actions :deep(.fv-Button) {
	font-size: 11px;
}
.bottom-bar {
	align-items: center;
	padding-top: 14px;
	color: #897e95;
	font-size: 13px;
}
.bottom-bar > div {
	display: flex;
	gap: 8px;
}
.mobile-users, .mobile-pagination { display: none; }
.load-error { color: #b13c60; margin: 14px 0; overflow-wrap: anywhere; }
.touch-button { min-height: 44px; min-width: 0; border: 1px solid #e1d8ee; border-radius: 8px; padding: 10px 14px; background: rgba(255,255,255,.85); color: #5d3679; font: inherit; font-size: 14px; cursor: pointer; touch-action: manipulation; }
.touch-button:disabled { opacity: .5; cursor: not-allowed; }
.touch-button:focus-visible, .user-link:focus-visible { outline: 2px solid #a56bd1; outline-offset: 3px; }
.permission-button { color: #fff; border-color: transparent; }
@media (max-width: 1024px) {
	.users-page {
		padding: 28px 18px;
	}
	.page-header {
		align-items: start;
		flex-wrap: wrap;
	}
	.toolbar {
		align-items: stretch;
		flex-direction: column;
	}
	.user-search {
		width: 100%;
	}
	.list-card, .desktop-pagination { display: none; }
	.mobile-users { display: grid; gap: 14px; min-width: 0; }
	.mobile-user-card { min-width: 0; padding: 18px; border: 1px solid rgba(255,255,255,.95); border-radius: 18px; background: rgba(255,255,255,.75); box-shadow: 0 12px 32px rgba(116,77,164,.08); }
	.mobile-user-heading { width: 100%; gap: 12px; margin-bottom: 16px; }
	.mobile-user-identity { min-width: 0; overflow-wrap: anywhere; }
	.mobile-user-heading .avatar-letter { width: 42px; height: 42px; font-size: 16px; }
	.mobile-user-details { display: grid; gap: 12px; margin: 0; }
	.mobile-user-details > div { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px; align-items: baseline; }
	.mobile-user-details dt { color: #8f839a; font-size: 12px; }
	.mobile-user-details dd { min-width: 0; margin: 0; color: #45375d; font-size: 14px; overflow-wrap: anywhere; }
	.mobile-user-roles dd { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
	.role-chip { display: inline-flex; flex-wrap: wrap; gap: 6px; align-items: center; max-width: 100%; padding: 5px 9px; border-radius: 8px; color: #39755a; background: #e8f4ee; }
	.role-chip code { font-size: 11px; overflow-wrap: anywhere; }
	.role-chip.role-admin { color: #95621e; background: #fff0d9; }
	.mobile-user-actions { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; margin-top: 18px; }
	.mobile-empty { padding: 40px 18px; color: #8c7e99; text-align: center; border: 1px dashed #d8c5e7; border-radius: 18px; }
	.bottom-bar {
		align-items: stretch;
		flex-direction: column;
		gap: 12px;
		padding-bottom: 25px;
	}
	.mobile-pagination { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%; }
}
@media (max-width: 360px) {
	.users-page { padding: 24px 12px; }
	.mobile-user-card { padding: 14px; }
	.mobile-user-actions { grid-template-columns: minmax(0, 1fr); }
}
.right-menu {
	min-width: 150px;
	padding: 4px;
}
.right-menu span {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 9px 11px;
	border-radius: 8px;
	color: #6e4c8d;
	cursor: pointer;
}
.right-menu i {
	color: #4b0d7a;
}
.right-menu p {
	margin: 0;
	color: rgba(36, 27, 56, 0.8);
	font-size: 13px;
}
</style>
