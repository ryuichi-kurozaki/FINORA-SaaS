import axios from "axios";
import { useCallback, useEffect, useState } from "react";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((cfg) => {
  const tk = localStorage.getItem("finora_token");
  if (tk) cfg.headers.Authorization = `Bearer ${tk}`;
  cfg.headers["X-Lang"] = localStorage.getItem("finora_lang") || "ja";
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const orig = err.config;
    if (err.response?.status === 401 && !orig._retry && !orig.url.includes("/auth/")) {
      orig._retry = true;
      try {
        const { data } = await axios.post(`${API}/auth/refresh`, {}, { withCredentials: true });
        localStorage.setItem("finora_token", data.access_token);
        return api(orig);
      } catch {
        localStorage.removeItem("finora_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Error";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return d.msg || String(d);
}

export function useApi(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      const r = await api.get(path);
      setData(r.data);
    } catch (e) {
      setData(null);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { load(); }, [load]);
  return { data, loading, reload: load, setData };
}

export async function downloadFile(path, filename) {
  const r = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
