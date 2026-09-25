import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";

export function useDashboard(clientOverride) {
  const { lang, scopeClient } = useApp();
  const cid = clientOverride ?? scopeClient;
  return useApi(`/analytics/dashboard?lang=${lang}${cid ? `&client_id=${cid}` : ""}`, [cid, lang]);
}

export function useScopeLabel() {
  const { t, scopeClient, clientName } = useApp();
  return scopeClient ? clientName(scopeClient) : t("all_clients");
}
