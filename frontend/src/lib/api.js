import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const listVoices = () => api.get("/voices").then((r) => r.data);

export const listProjects = () => api.get("/projects").then((r) => r.data);

export const getProject = (id) =>
  api.get(`/projects/${id}`).then((r) => r.data);

export const createProject = (payload) =>
  api.post("/projects", payload).then((r) => r.data);

export const deleteProject = (id) =>
  api.delete(`/projects/${id}`).then((r) => r.data);

export const uploadFiles = (id, files, onProgress) => {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return api
    .post(`/projects/${id}/upload`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) =>
        onProgress && e.total && onProgress(Math.round((e.loaded * 100) / e.total)),
    })
    .then((r) => r.data);
};

export const processProject = (id) =>
  api.post(`/projects/${id}/process`).then((r) => r.data);

export const downloadUrl = (id) => `${API}/projects/${id}/download`;
export const streamUrl = (id) => `${API}/projects/${id}/stream`;
