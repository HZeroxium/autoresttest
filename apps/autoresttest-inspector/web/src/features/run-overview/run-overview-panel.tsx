import ReactECharts from "echarts-for-react";

import { Panel } from "@/components/common/panel";
import { RunBundleSummary, TimelinePage } from "@/lib/schemas/api";
import {
  formatCompactNumber,
  formatDate,
  formatNumber,
} from "@/lib/formatters/format";

type RunOverviewPanelProps = {
  run: RunBundleSummary;
  timeline?: TimelinePage;
};

function buildStatusSeries(run: RunBundleSummary) {
  const statusMap = (run.report?.["Status Code Distribution"] ?? {}) as Record<
    string,
    number
  >;
  return Object.entries(statusMap).map(([name, value]) => ({ name, value }));
}

export function RunOverviewPanel({ run, timeline }: RunOverviewPanelProps) {
  const statusSeries = buildStatusSeries(run);
  const events = timeline?.events ?? [];
  const logicalEvents = events.filter((event) => event.traceKind === "logical_request");
  const httpEvents = events.filter((event) => event.traceKind === "http_attempt");
  const llmEvents = events.filter((event) => event.traceKind === "llm_call");
  const slowest = [...logicalEvents]
    .sort((a, b) => (b.durationMs ?? 0) - (a.durationMs ?? 0))
    .slice(0, 5);

  return (
    <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
      <div className="space-y-4">
        <Panel title="Run summary">
          <div className="grid gap-3 md:grid-cols-3">
            <MetricCard
              label="Run status"
              value={run.manifest.status}
              note={formatDate(run.manifest.updatedAt)}
            />
            <MetricCard
              label="Requests sent"
              value={formatNumber(
                Number(run.report?.["Total Requests Sent"] ?? 0),
              )}
              note={`${formatCompactNumber(httpEvents.length)} traced attempts`}
            />
            <MetricCard
              label="Successful operations"
              value={formatNumber(
                Number(run.report?.["Number of Successfully Processed Operations"] ?? 0),
              )}
              note={`${formatCompactNumber(logicalEvents.length)} logical spans`}
            />
            <MetricCard
              label="LLM calls"
              value={formatNumber(run.traceCounts.llm_calls ?? 0)}
              note={`${formatCompactNumber(llmEvents.length)} events in page`}
            />
            <MetricCard
              label="Timeline ordering"
              value={timeline?.timelineOrder ?? "n/a"}
              note={timeline?.warnings[0] ?? "Stable merged order"}
            />
            <MetricCard
              label="Warnings"
              value={formatNumber(run.warnings.length)}
              note={run.warnings[0] ?? "No warnings"}
            />
          </div>
        </Panel>

        <Panel title="Top anomalies">
          <div className="grid gap-3 md:grid-cols-2">
            <AnomalyRow
              label="4xx heavy run"
              value={statusSeries
                .filter((item) => item.name.startsWith("4"))
                .reduce((sum, item) => sum + item.value, 0)}
            />
            <AnomalyRow
              label="Zero 2xx coverage"
              value={statusSeries.every((item) => !item.name.startsWith("2")) ? 1 : 0}
            />
            <AnomalyRow
              label="Slowest logical span"
              value={
                slowest[0]?.durationMs
                  ? `${slowest[0].durationMs.toFixed(1)} ms`
                  : "n/a"
              }
            />
            <AnomalyRow
              label="Most retried phase"
              value={
                run.phaseSummaries["marl_request_generation"]?.http_attempt ??
                run.phaseSummaries["value_agent_q_table_generation"]?.http_attempt ??
                0
              }
            />
          </div>
        </Panel>
      </div>

      <Panel title="Status code distribution">
        <ReactECharts
          notMerge
          option={{
            tooltip: { trigger: "item" },
            series: [
              {
                type: "pie",
                radius: ["40%", "72%"],
                label: { color: "#12343b" },
                data: statusSeries,
                itemStyle: { borderRadius: 8 },
              },
            ],
            color: ["#12343b", "#d28b36", "#365f64", "#f0c38b", "#5f6f72"],
          }}
          style={{ height: 320 }}
        />
      </Panel>
    </div>
  );
}

function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string | number;
  note?: string;
}) {
  return (
    <div className="rounded-2xl bg-paper p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate">{label}</div>
      <div className="mt-2 font-display text-2xl font-semibold text-ink">{value}</div>
      {note ? <div className="mt-1 text-xs text-slate">{note}</div> : null}
    </div>
  );
}

function AnomalyRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-line bg-paper p-4">
      <div className="text-sm font-medium text-ink">{label}</div>
      <div className="mt-1 text-xl font-semibold text-accent">{value}</div>
    </div>
  );
}
