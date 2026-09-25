import { useApp } from "@/context/AppContext";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { PageHeader, Spinner } from "@/components/common";
import GoalsPanel from "@/components/GoalsPanel";
import HealthPanel from "@/components/HealthPanel";
import EntityManager from "@/components/EntityManager";

export function GoalsPage() {
  const { t, scopeClient } = useApp();
  const scope = useScopeLabel();
  const { data, reload } = useDashboard();
  return (
    <div className="space-y-6" data-testid="goals-page">
      <PageHeader eyebrow={`Goals · ${scope}`} title={t("goals")} />
      {data ? <GoalsPanel goals={data.goals} /> : <Spinner />}
      <EntityManager key={scopeClient} entity="goals" onChange={reload} />
    </div>
  );
}

export function DataHealthPage() {
  const { t, scopeClient } = useApp();
  const scope = useScopeLabel();
  const { data } = useDashboard();
  return (
    <div data-testid="data-health-page">
      <PageHeader eyebrow={`Data Health · ${scope}`} title={t("data_health")} />
      {data ? <HealthPanel health={data.health} clientId={scopeClient} /> : <Spinner />}
    </div>
  );
}
