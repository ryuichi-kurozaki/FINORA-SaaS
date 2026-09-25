import { useApp } from "@/context/AppContext";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { Card, CardTitle, PageHeader, Spinner } from "@/components/common";
import InsightPanel from "@/components/InsightPanel";
import AIAssistant from "@/components/AIAssistant";

export default function AIInsight() {
  const { t, scopeClient } = useApp();
  const { data } = useDashboard();
  const scope = useScopeLabel();
  return (
    <div data-testid="ai-insight-page">
      <PageHeader eyebrow={`AI Intelligence · ${scope}`} title={t("ai_insight")} sub={t("ai_engine_note")} />
      <div className="grid gap-6 2xl:grid-cols-[1.4fr_1fr]">
        {data ? <InsightPanel insights={data.insights} /> : <Spinner />}
        <Card className="flex h-[720px] flex-col">
          <CardTitle>{t("ask_ai")}</CardTitle>
          <div className="min-h-0 flex-1"><AIAssistant key={scopeClient} clientId={scopeClient} /></div>
        </Card>
      </div>
    </div>
  );
}
