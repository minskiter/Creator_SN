import client from "./config.js";
import { User } from "./api.js";

const request = (method, url, data, config = {}) =>
  client({ method, url, data, ...config }).then((response) => response.data);

export const UserApi = {
  login: (payload) => User.Login(payload),
  register: (payload) => User.ApplyUser(payload),
  me: () => User.GetUserInfo(),
  updateMe: (payload) => User.UpdateUserInfo(null, payload),
  updatePassword: (payload) => User.UpdateUserPassword(null, payload),
  uploadAvatar: (file, onUploadProgress) => {
    const form = new FormData();
    form.append("user_avatar", file);
    return User.UploadAvatar(null, form, undefined, onUploadProgress);
  },
  avatar: () => User.GetMyAvatar(),
  list: (search, offset, limit) => User.ListUsers(search, offset, limit),
  count: (search) => User.GetTotalUserCount(search),
  roles: () => User.GetAllUserRoles(),
  resetPassword: (userid) => User.ResetUserPassword(null, { userid, pwd: "", confirm_pwd: "" }),
  addRole: (userid, role) => User.AddUserRole({ userid, role }),
  removeRole: (userid, role) => User.RemoveUserRole({ userid, role }),
  userAvatar: (userid) => User.GetUserAvatar(userid)
};

export const ResumeApi = {
  list: () => request("get", "/resume/list"),
  mine: () => request("get", "/resume/mine"),
  save: (payload) => request("post", "/resume/save", payload),
  remove: (id) => request("delete", `/resume/${id}`),
  uploadImage: (id, file, onUploadProgress) => {
    const form = new FormData();
    form.append("id", id);
    form.append("image", file, "image.jpg");
    return request("post", "/resume/upload_image", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress,
    });
  },
  imageUrl: (id, imageName) =>
    `${client.defaults.baseURL}/resume/image/${encodeURIComponent(id)}/${encodeURIComponent(imageName)}`
};

export const ProjectApi = {
  featured: () => request("get", "/projects/featured"),
  list: (search, offset = 0, limit = 12) => request("get", "/projects/list", undefined, { params: { search, offset, limit } }),
  adminList: (search, offset = 0, limit = 99999) => request("get", "/projects/admin/list", undefined, { params: { search, offset, limit } }),
  save: (payload) => request("post", "/projects/update", payload),
  remove: (id) => request("delete", `/projects/${id}`),
  uploadIcon: (id, file) => {
    const form = new FormData();
    form.append("icon", file);
    return request("post", `/projects/upload_icon?id=${encodeURIComponent(id)}`, form, { headers: { "Content-Type": "multipart/form-data" } });
  },
  iconUrl: (id) => `${client.defaults.baseURL}/projects/icon/${id}`
};

export { client as axios, User };

export const OIDCApi = {
  list: () => request("get", "/oidc/clients"),
  create: (body) => request("post", "/oidc/clients", body),
  update: (id, body) => request("put", `/oidc/clients/${encodeURIComponent(id)}`, body),
  remove: (id) => request("delete", `/oidc/clients/${encodeURIComponent(id)}`),
  rotate: (id) => request("post", `/oidc/clients/${encodeURIComponent(id)}/rotate-secret`),
  preview: (body) => request("post", "/oidc/authorize/preview", body),
  authorize: (body) => request("post", "/oidc/authorize", body)
};
