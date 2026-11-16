<template>
	<div class="manage-container">
		<div class="manage-content-block">
			<fv-navigation-view
				v-model="currentNav"
				theme="light"
				:title="local('Console')"
				:options="navList"
				v-model:expand="isExpand"
				foreground="#a56bd1"
				background="transparent"
				:flyout-display="1368"
				:mobile-display="1024"
				class="navigation-view"
				:show-setting="false"
				@item-click="handleItemClick"
				@back="$Back()"
			></fv-navigation-view
			><router-view></router-view>
		</div>
	</div>
</template>
<script>
import { useAppStore } from "@/store";

export default {
	name: "AdminLayout",
	data() {
		return {
			currentNav: {},
			isExpand: true,
			navList: [
				{
					key: 0,
					name: () => this.local("User Management"),
					icon: "GuestUser",
					route: "/admin/users",
				},
				{
					key: 1,
					name: () => this.local("Resume Management"),
					icon: "ReadingMode",
					route: "/admin/resumes",
				},
				{
					key: 3,
					name: () => "OIDC 应用管理",
					icon: "AppIconDefault",
					route: "/admin/applications",
				},
				{
					key: 2,
					name: () => this.local("Project Management"),
					icon: "ProductList",
					route: "/admin/projects",
				},
				{ key: -1, name: () => this.local("Home"), icon: "Home", route: "/" },
			],
		};
	},
	mounted() {
		this.routeFormat();
	},
	watch: {
		$route() {
			this.routeFormat();
		},
	},
	methods: {
		local(text, params) {
			return useAppStore().local(text, params);
		},
		handleItemClick(item) {
			this.$Go(item.route);
		},
		routeFormat() {
			this.currentNav =
				this.navList.find((item) => this.$route.path === item.route) ||
				this.navList[0];
		},
	},
};
</script>
<style scoped lang="scss">
.manage-container {
	position: absolute;
	inset: 0;
	overflow: hidden;
	background: linear-gradient(145deg, #fbf9ff, #f0ebff 52%, #eaf9ff);
}
.manage-content-block {
	display: flex;
	width: 100%;
	height: 100%;
	overflow: hidden;
}
.navigation-view {
	z-index: 2;
	--fv-navigation-background: rgba(255, 255, 255, 0.78);
}
</style>
