import { PropsWithChildren, ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import clsx from "clsx";

import { LiveIndicator } from "@/features/live-monitor/live-indicator";
import { DatasetSummary, RunManifestSummary } from "@/lib/schemas/api";

type AppShellProps = PropsWithChildren<{
  datasets: DatasetSummary[];
  runs?: RunManifestSummary[];
  selectedDatasetId?: string;
  selectedRunId?: string;
  title: string;
  subtitle?: string;
  headerContent?: ReactNode;
}>;

export function AppShell({
  datasets,
  runs = [],
  selectedDatasetId,
  selectedRunId,
  title,
  subtitle,
  headerContent,
  children,
}: AppShellProps) {
  return (
    <div className="min-h-full px-4 py-4 lg:px-6">
      <div className="grid min-h-[calc(100vh-2rem)] grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="rounded-3xl border border-line bg-panel/90 p-4 shadow-panel backdrop-blur-sm">
          <div className="mb-5">
            <div className="font-display text-xl font-bold text-ink">
              AutoRestTest Inspector
            </div>
            <p className="mt-1 text-sm text-slate">
              Local-first analysis console for artifacts, traces, and graph state.
            </p>
          </div>

          <div className="space-y-6">
            <section>
              <div className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate">
                Datasets
              </div>
              <div className="space-y-2">
                {datasets.map((dataset) => {
                  const active = dataset.datasetId === selectedDatasetId;
                  return (
                    <Link
                      key={dataset.datasetId}
                      to="/datasets/$datasetId"
                      params={{ datasetId: dataset.datasetId }}
                      className={clsx(
                        "block rounded-2xl border px-3 py-3 transition-colors",
                        active
                          ? "border-ink bg-ink text-paper"
                          : "border-line bg-paper text-ink hover:border-accent hover:bg-accentSoft/50",
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium">{dataset.datasetId}</span>
                        <span className="rounded-full bg-black/10 px-2 py-0.5 text-[11px] uppercase tracking-wide">
                          {dataset.latestRunStatus ?? "idle"}
                        </span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </section>

            {selectedDatasetId && runs.length > 0 && (
              <section>
                <div className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate">
                  Runs
                </div>
                <div className="max-h-[42vh] space-y-2 overflow-auto pr-1">
                  {runs.map((run) => {
                    const active = run.runId === selectedRunId;
                    return (
                      <Link
                        key={run.runId}
                        to="/datasets/$datasetId/runs/$runId"
                        params={{ datasetId: selectedDatasetId, runId: run.runId }}
                        className={clsx(
                          "block rounded-2xl border px-3 py-3 text-sm transition-colors",
                          active
                            ? "border-accent bg-accent text-white"
                            : "border-line bg-paper text-ink hover:border-accent hover:bg-accentSoft/50",
                        )}
                      >
                        <div className="font-mono text-xs">{run.runId}</div>
                        <div className="mt-1 text-[11px] uppercase tracking-wide opacity-80">
                          {run.status}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        </aside>

        <main className="space-y-4">
          <header className="rounded-3xl border border-line bg-panel/90 px-6 py-5 shadow-panel backdrop-blur-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h1 className="font-display text-3xl font-bold text-ink">{title}</h1>
                {subtitle ? (
                  <p className="mt-1 text-sm text-slate">{subtitle}</p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <LiveIndicator />
                {headerContent}
              </div>
            </div>
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}
