import { Link } from "@tanstack/react-router";

import { Panel } from "@/components/common/panel";
import { DatasetSummary } from "@/lib/schemas/api";
import { formatDate } from "@/lib/formatters/format";

type DatasetDashboardProps = {
  datasets: DatasetSummary[];
};

export function DatasetDashboard({ datasets }: DatasetDashboardProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {datasets.map((dataset) => (
        <Panel key={dataset.datasetId} className="flex flex-col">
          <div className="mb-4">
            <div className="font-display text-xl font-semibold text-ink">
              {dataset.datasetId}
            </div>
            <div className="mt-1 text-sm text-slate">
              Latest run: {dataset.latestRunId ?? "none"}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl bg-paper p-3">
              <div className="text-xs uppercase tracking-wide text-slate">Status</div>
              <div className="mt-1 font-medium text-ink">
                {dataset.latestRunStatus ?? "n/a"}
              </div>
            </div>
            <div className="rounded-2xl bg-paper p-3">
              <div className="text-xs uppercase tracking-wide text-slate">Updated</div>
              <div className="mt-1 font-medium text-ink">
                {formatDate(dataset.latestUpdatedAt)}
              </div>
            </div>
            <div className="rounded-2xl bg-paper p-3">
              <div className="text-xs uppercase tracking-wide text-slate">Graph cache</div>
              <div className="mt-1 font-medium text-ink">
                {dataset.hasGraphCache ? "Yes" : "No"}
              </div>
            </div>
            <div className="rounded-2xl bg-paper p-3">
              <div className="text-xs uppercase tracking-wide text-slate">Q-table cache</div>
              <div className="mt-1 font-medium text-ink">
                {dataset.hasQtableCache ? "Yes" : "No"}
              </div>
            </div>
          </div>

          <div className="mt-5">
            <Link
              to="/datasets/$datasetId"
              params={{ datasetId: dataset.datasetId }}
              className="inline-flex rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper transition-colors hover:bg-inkSoft"
            >
              Open dataset
            </Link>
          </div>
        </Panel>
      ))}
    </div>
  );
}
