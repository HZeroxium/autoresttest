import { Navigate } from "@tanstack/react-router";

import { AppLayout } from "@/app/layout";
import { DatasetDashboard } from "@/features/dataset-browser/dataset-dashboard";
import { useDataset, useDatasets, useRuns } from "@/lib/api/hooks";

type DatasetRoutePageProps = {
  datasetId: string;
};

export function DatasetRoutePage({ datasetId }: DatasetRoutePageProps) {
  const datasetsQuery = useDatasets();
  const datasetQuery = useDataset(datasetId);
  const runsQuery = useRuns(datasetId);
  const latestRunId = datasetQuery.data?.latestRun?.runId;

  if (latestRunId) {
    return (
      <Navigate
        to="/datasets/$datasetId/runs/$runId"
        params={{ datasetId, runId: latestRunId }}
        replace
      />
    );
  }

  return (
    <AppLayout
      datasets={datasetsQuery.data ?? []}
      runs={runsQuery.data ?? []}
      selectedDatasetId={datasetId}
      title={datasetQuery.data?.dataset.datasetId ?? datasetId}
      subtitle="Preparing the latest run workspace..."
    >
      <DatasetDashboard datasets={datasetsQuery.data ?? []} />
    </AppLayout>
  );
}
