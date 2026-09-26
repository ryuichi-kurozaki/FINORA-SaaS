import { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";

const cache = {};

export function useSite() {
  const { lang } = useApp();
  const [data, setData] = useState(cache[lang] || null);
  useEffect(() => {
    if (cache[lang]) { setData(cache[lang]); return; }
    api.get(`/public/site?lang=${lang}`).then((r) => { cache[lang] = r.data; setData(r.data); }).catch(() => setData({ settings: {}, services: [], faqs: [], history: [], news: [] }));
  }, [lang]);
  return data;
}

export const clearSiteCache = () => Object.keys(cache).forEach((k) => delete cache[k]);

export const imgSrc = (u) => (u && u.startsWith("/api/") ? `${process.env.REACT_APP_BACKEND_URL || ""}${u}` : u);
