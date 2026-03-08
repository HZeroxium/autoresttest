import { useDeferredValue, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";

import { Panel } from "@/components/common/panel";
import { DatasetSummary } from "@/lib/schemas/api";
import { formatCompactNumber, formatDate } from "@/lib/formatters/format";

type DatasetDashboardProps = {
  datasets: DatasetSummary[];
};

type SortMode = "updated" | "tokens" | "requests" | "name";

export function DatasetDashboard({ datasets }: DatasetDashboardProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("updated");
  const deferredSearch = useDeferredValue(search);

  const summary = useMemo(
    () => ({
      datasets: datasets.length,
      running: datasets.filter((dataset) => dataset.latestRunStatus === "running").length,
      unstable: datasets.filter((dataset) =>
        ["failed", "interrupted"].includes(dataset.latestRunStatus ?? ""),
      ).length,
      tokenized: datasets.filter((dataset) => (dataset.latestTotalTokens ?? 0) > 0).length,
    }),
    [datasets],
  );

  const filteredDatasets = useMemo(() => {
    const searchText = deferredSearch.trim().toLowerCase();
    const filtered = datasets.filter((dataset) => {
      if (
        searchText &&
        !dataset.datasetId.toLowerCase().includes(searchText) &&
        !(dataset.latestRunId ?? "").toLowerCase().includes(searchText)
      ) {
        return false;
      }
      if (statusFilter !== "all" && (dataset.latestRunStatus ?? "unknown") !== statusFilter) {
        return false;
      }
      return true;
    });

    filtered.sort((left, right) => {
      if (sortMode === "tokens") {
        return (right.latestTotalTokens ?? 0) - (left.latestTotalTokens ?? 0);
      }
      if (sortMode === "requests") {
        return (
          (right.latestTotalRequestsSent ?? 0) - (left.latestTotalRequestsSent ?? 0)
        );
      }
      if (sortMode === "name") {
        return left.datasetId.localeCompare(right.datasetId);
      }
      const leftTime = left.latestUpdatedAt ? new Date(left.latestUpdatedAt).getTime() : 0;
      const rightTime = right.latestUpdatedAt ? new Date(right.latestUpdatedAt).getTime() : 0;
      return rightTime - leftTime;
    });
    return filtered;
  }, [datasets, deferredSearch, sortMode, statusFilter]);

  const statuses = Array.from(
    new Set(datasets.map((dataset) => dataset.latestRunStatus ?? "unknown")),
  ).sort();

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Datasets" value={String(summary.datasets)} note="Valid run-scoped datasets" />
        <StatCard label="Running" value={String(summary.running)} note="Latest run still active" />
        <StatCard label="Failed / Interrupted" value={String(summary.unstable)} note="Needs review" />
        <StatCard label="With token usage" value={String(summary.tokenized)} note="Latest run has LLM usage" />
      </div>

      <Panel
        title="Dataset workspace"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search dataset or run..."
              className="w-full min-w-[220px] rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none sm:w-auto"
            />
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none"
            >
              <option value="all">All statuses</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
            <select
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
              className="rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none"
            >
              <option value="updated">Sort: Updated</option>
              <option value="tokens">Sort: Tokens</option>
              <option value="requests">Sort: Requests</option>
              <option value="name">Sort: Name</option>
            </select>
          </div>
        }
      >
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {filteredDatasets.map((dataset) => (
            <Panel key={dataset.datasetId} className="flex h-full flex-col bg-paper/80">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-display text-xl font-semibold text-ink">
                    {dataset.datasetId}
                  </div>
                  <div className="mt-1 text-sm text-slate">
                    Latest run: {dataset.latestRunId ?? "none"}
                  </div>
                </div>
                <span className="rounded-full border border-line bg-panel px-3 py-1 text-xs uppercase tracking-wide text-slate">
                  {dataset.latestRunStatus ?? "unknown"}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <MetricTile
                  label="Updated"
                  value={formatDate(dataset.latestUpdatedAt)}
                />
                <MetricTile
                  label="Requests"
                  value={formatCompactNumber(dataset.latestTotalRequestsSent)}
                />
                <MetricTile
                  label="Tokens"
                  value={formatCompactNumber(dataset.latestTotalTokens)}
                />
                <MetricTile
                  label="Schema"
                  value={dataset.latestReportSchema ?? "unknown"}
                />
              </div>

              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate">
                <Badge active={dataset.hasTraceArtifacts}>Trace</Badge>
                <Badge active={dataset.hasGraphCache}>Graph cache</Badge>
                <Badge active={dataset.hasQtableCache}>Q-table cache</Badge>
                <Badge active={dataset.hasDataArtifacts}>Artifacts</Badge>
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
      </Panel>
    </div>
  );
}

function StatCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <Panel className="bg-paper/80">
      <div className="text-xs uppercase tracking-[0.18em] text-slate">{label}</div>
      <div className="mt-2 font-display text-3xl font-semibold text-ink">{value}</div>
      <div className="mt-1 text-sm text-slate">{note}</div>
    </Panel>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-panel px-3 py-3">
      <div className="text-xs uppercase tracking-wide text-slate">{label}</div>
      <div className="mt-1 font-medium text-ink">{value}</div>
    </div>
  );
}

function Badge({ active, children }: { active: boolean; children: string }) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 ${
        active ? "bg-accentSoft text-ink" : "bg-panel text-slate"
      }`}
    >
      {children}
    </span>
  );
}
