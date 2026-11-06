import { createRouter, createWebHashHistory } from "vue-router";
import tool from "./tools";

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      redirect: "/home"
    },
    {
      path: "/home",
      name: "Home",
      component: tool.AsyncLoad(() => import("@/views/home/index.vue")),
      meta: { title: "创造者官网" },
      children: [
        { path: "", name: "HomeLanding", component: tool.AsyncLoad(() => import("@/views/home/HomeLanding.vue")), meta: { title: "创造者官网" } },
        { path: "projects", name: "Projects", component: tool.AsyncLoad(() => import("@/views/home/AllProjects.vue")), meta: { title: "项目 · Creator SN" } },
        { path: "join", name: "Join", component: tool.AsyncLoad(() => import("@/views/home/JoinUs.vue")), meta: { title: "加入我们 · Creator SN" } },
        { path: "team", name: "Team", component: tool.AsyncLoad(() => import("@/views/team/index.vue")), meta: { title: "团队 · Creator SN" } }
      ]
    },
    {
      path: "/dev",
      name: "Dev",
      component: tool.AsyncLoad(() => import("@/views/dev/index.vue"))
    },
    {
      path: "/login",
      name: "Login",
      component: tool.AsyncLoad(() => import("@/views/auth/AuthLayout.vue")),
      children: [
        { path: "", name: "LoginForm", component: tool.AsyncLoad(() => import("@/views/auth/LoginView.vue")) },
        { path: "register", name: "Register", component: tool.AsyncLoad(() => import("@/views/auth/RegisterView.vue")) }
      ]
    },
    {
      path: "/oauth/authorize",
      component: tool.AsyncLoad(() => import("@/views/auth/OIDCAuthorizeView.vue")),
      meta: { requiresAuth: true, title: "应用授权 · Creator SN" }
    },
    {
      path: "/profile",
      name: "Profile",
      component: tool.AsyncLoad(() => import("@/views/profile/ProfileView.vue")),
      meta: { requiresAuth: true, title: "个人中心 · Creator SN" }
    },
    {
      path: "/admin",
      component: tool.AsyncLoad(() => import("@/views/admin/AdminLayout.vue")),
      meta: { requiresAuth: true, requiresAdmin: true, title: "用户管理 · Creator SN" },
      children: [
        { path: "", redirect: "/admin/users" },
        { path: "applications", name: "AdminApplications", component: tool.AsyncLoad(() => import("@/views/admin/AdminApplicationsView.vue")), meta: { title: "应用管理 · Creator SN" } },
        { path: "users", name: "AdminUsers", component: tool.AsyncLoad(() => import("@/views/admin/AdminUsersView.vue")) },
        { path: "projects", name: "AdminProjects", component: tool.AsyncLoad(() => import("@/views/admin/AdminProjectsView.vue")) },
        { path: "resumes", name: "AdminResumes", component: tool.AsyncLoad(() => import("@/views/admin/AdminResumesView.vue")) }
      ]
    }
  ]
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem("ApiToken")) {
    return { path: "/login", query: { return_url: to.fullPath } };
  }
  if (to.meta.requiresAdmin && !String(localStorage.getItem("ApiUserRole") || "").split(",").includes("admin")) {
    return { path: "/home", query: { denied: "admin" } };
  }
  if (to.meta.title) document.title = to.meta.title;
  return true;
});

export default router;
