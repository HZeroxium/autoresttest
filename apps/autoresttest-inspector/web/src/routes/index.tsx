import { AppLayout } from "@/app/layout";
import { DatasetDashboard } from "@/features/dataset-browser/dataset-dashboard";
import { useDatasets } from "@/lib/api/hooks";

export function IndexRoutePage() {
  const datasetsQuery = useDatasets();
  const datasets = datasetsQuery.data ?? [];

  return (
    <AppLayout
      datasets={datasets}
      title="Dataset workspace"
      subtitle="Browse local AutoRestTest datasets, pick a run, and drill into runtime observability."
    >
      <DatasetDashboard datasets={datasets} />
    </AppLayout>
  );
}
