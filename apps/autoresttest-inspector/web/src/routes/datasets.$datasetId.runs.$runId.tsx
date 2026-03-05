import { startTransition } from "react";
import * as Tabs from "@radix-ui/react-tabs";

import { AppLayout } from "@/app/layout";
import { ArtifactsPanel } from "@/features/artifacts-browser/artifacts-panel";
import { QTablePanel } from "@/features/qtable-browser/qtable-panel";
import { RunComparePanel } from "@/features/run-compare/run-compare-panel";
import { RunOverviewPanel } from "@/features/run-overview/run-overview-panel";
import { SemanticGraphPanel } from "@/features/semantic-graph/semantic-graph-panel";
import { TraceExplorerPanel } from "@/features/trace-explorer/trace-explorer-panel";
import {
  useArtifacts,
  useCachedQtables,
  useDataset,
  useDatasets,
  useGraph,
  useRun,
  useRuns,
  useRuntimeQtables,
  useTimeline,
} from "@/lib/api/hooks";
import { formatDate } from "@/lib/formatters/format";
import { useInspectorStore } from "@/lib/state/inspector-store";

type RunRoutePageProps = {
  datasetId: string;
  runId: string;
};

export function RunRoutePage({ datasetId, runId }: RunRoutePageProps) {
  const datasetsQuery = useDatasets();
  const datasetQuery = useDataset(datasetId);
  const runsQuery = useRuns(datasetId);
  const runQuery = useRun(datasetId, runId);
  const graphQuery = useGraph(datasetId, runId);
  const runtimeQtablesQuery = useRuntimeQtables(datasetId, runId);
  const cachedQtablesQuery = useCachedQtables(datasetId);
  const artifactsQuery = useArtifacts(datasetId, runId);
  const timelineQuery = useTimeline(datasetId, runId);

  const activeTab = useInspectorStore((state) => state.activeTab);
  const setActiveTab = useInspectorStore((state) => state.setActiveTab);
  const run = runQuery.data;

  return (
    <AppLayout
      datasets={datasetsQuery.data ?? []}
      runs={runsQuery.data ?? []}
      selectedDatasetId={datasetId}
      selectedRunId={runId}
      title={datasetQuery.data?.dataset.datasetId ?? datasetId}
      subtitle={
        run
          ? `Run ${run.manifest.runId} | ${run.manifest.status} | updated ${formatDate(run.manifest.updatedAt)}`
          : "Loading run workspace..."
      }
      headerContent={
        <span className="rounded-full border border-line bg-paper px-3 py-2 text-sm text-slate">
          {run?.manifest.status ?? "loading"}
        </span>
      }
    >
      <Tabs.Root
        value={activeTab}
        onValueChange={(value) => {
          startTransition(() => setActiveTab(value));
        }}
        className="space-y-4"
      >
        <Tabs.List className="flex flex-wrap gap-2">
          {[
            ["overview", "Overview"],
            ["graph", "Semantic Graph"],
            ["qtables", "Q-Tables"],
            ["traces", "Trace Explorer"],
            ["artifacts", "Artifacts"],
            ["compare", "Compare"],
          ].map(([value, label]) => (
            <Tabs.Trigger
              key={value}
              value={value}
              className="rounded-full border border-line bg-paper px-4 py-2 text-sm text-ink transition-colors data-[state=active]:border-accent data-[state=active]:bg-accent data-[state=active]:text-white"
            >
              {label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="overview">
          {run ? <RunOverviewPanel run={run} timeline={timelineQuery.data} /> : null}
        </Tabs.Content>
        <Tabs.Content value="graph">
          <SemanticGraphPanel
            datasetId={datasetId}
            runId={runId}
            graph={graphQuery.data}
          />
        </Tabs.Content>
        <Tabs.Content value="qtables">
          <QTablePanel
            runtimeQtables={runtimeQtablesQuery.data}
            cachedQtables={cachedQtablesQuery.data}
          />
        </Tabs.Content>
        <Tabs.Content value="traces">
          <TraceExplorerPanel
            datasetId={datasetId}
            runId={runId}
            runStatus={run?.manifest.status ?? "unknown"}
          />
        </Tabs.Content>
        <Tabs.Content value="artifacts">
          <ArtifactsPanel
            datasetId={datasetId}
            runId={runId}
            artifacts={artifactsQuery.data}
          />
        </Tabs.Content>
        <Tabs.Content value="compare">
          <RunComparePanel
            datasetId={datasetId}
            currentRunId={runId}
            runs={runsQuery.data ?? []}
          />
        </Tabs.Content>
      </Tabs.Root>
    </AppLayout>
  );
}
