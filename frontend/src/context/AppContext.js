import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { translate } from "@/i18n/dict";
import { OWNED } from "@/config/entities";

const Ctx = createContext(null);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [lang, setLangState] = useState(localStorage.getItem("finora_lang") || "ja");
  const [clients, setClients] = useState([]);
  const [scopeClient, setScopeClient] = useState("");

  const t = useCallback((k) => translate(lang, k), [lang]);
  const setLang = (l) => {
    setLangState(l);
    localStorage.setItem("finora_lang", l);
    if (user) api.put("/auth/preferences", { lang: l }).catch(() => {});
  };

  const refreshClients = useCallback(async () => {
    const r = await api.get("/data/clients");
    setClients(r.data);
  }, []);

  useEffect(() => {
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => setUser(false));
  }, []);

  useEffect(() => {
    if (user) {
      refreshClients();
      if (user.role === "client") setScopeClient(user.client_id);
    }
  }, [user, refreshClients]);

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const logout = async () => {
    await api.post("/auth/logout").catch(() => {});
    localStorage.removeItem("finora_token");
    setUser(false);
    setScopeClient("");
  };

  const clientName = (id) => {
    const c = clients.find((x) => x.id === id);
    return c ? c.corporate_name || c.name : "";
  };

  const canWrite = user && user.role !== "client";
  const isClient = user && user.role === "client";
  const canEdit = (entity, row) => {
    if (!user) return false;
    if (OWNED.includes(entity)) return isClient;
    if (entity === "tasks") return !row || row.owner_id === user.id;
    return !isClient;
  };
  return (
    <Ctx.Provider value={{ user, setUser, lang, setLang, t, clients, refreshClients, scopeClient, setScopeClient, logout, clientName, canWrite, isClient, canEdit }}>
      {children}
    </Ctx.Provider>
  );
}

export const useApp = () => useContext(Ctx);
