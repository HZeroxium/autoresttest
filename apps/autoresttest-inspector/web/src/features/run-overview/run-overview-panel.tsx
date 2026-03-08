import ReactECharts from "echarts-for-react";
import { Alert } from "@mui/material";

import { Panel } from "@/components/common/panel";
import {
  OperationMetricsResponse,
  RunBundleSummary,
  TimelinePage,
} from "@/lib/schemas/api";
import {
  formatCompactNumber,
  formatDate,
  formatNumber,
} from "@/lib/formatters/format";

type RunOverviewPanelProps = {
  run: RunBundleSummary;
  timeline?: TimelinePage;
  operationMetrics?: OperationMetricsResponse;
};

function buildStatusSeries(run: RunBundleSummary) {
  const statusMap = run.reportMetrics?.statusCodeDistribution ?? {};
  return Object.entries(statusMap).map(([name, value]) => ({ name, value }));
}

function buildPhaseSeries(run: RunBundleSummary) {
  return Object.entries(run.phaseSummaries).map(([phase, counts]) => ({
    phase,
    logical: counts.logical_request ?? 0,
    http: counts.http_attempt ?? 0,
    llm: counts.llm_call ?? 0,
  }));
}

export function RunOverviewPanel({
  run,
  timeline,
  operationMetrics,
}: RunOverviewPanelProps) {
  const metrics = run.reportMetrics;
  const statusSeries = buildStatusSeries(run);
  const phaseSeries = buildPhaseSeries(run);
  const events = timeline?.events ?? [];
  const logicalEvents = events.filter((event) => event.traceKind === "logical_request");
  const httpEvents = events.filter((event) => event.traceKind === "http_attempt");
  const llmEvents = events.filter((event) => event.traceKind === "llm_call");
  const statusMap = metrics?.statusCodeDistribution ?? {};
  const fourXx = Object.entries(statusMap)
    .filter(([code]) => code.startsWith("4"))
    .reduce((sum, [, count]) => sum + count, 0);
  const fiveXx = Object.entries(statusMap)
    .filter(([code]) => code.startsWith("5"))
    .reduce((sum, [, count]) => sum + count, 0);
  const warnings: string[] = [];
  if (metrics?.reportSchema === "legacy_report") {
    warnings.push("This run uses a legacy report schema; some metrics are derived.");
  }
  if ((metrics?.derivedFields?.length ?? 0) > 0) {
    warnings.push(`Derived fields: ${metrics?.derivedFields.join(", ")}.`);
  }
  warnings.push(...run.warnings);

  const topExpensiveOperations = [...(operationMetrics?.operations ?? [])]
    .sort((left, right) => right.totalTokenCount - left.totalTokenCount)
    .slice(0, 5);

  return (
    <div className="space-y-4">
      {warnings.length > 0 ? (
        <Alert severity="warning" variant="outlined">
          {warnings.join(" ")}
        </Alert>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
        <MetricCard
          label="Run status"
          value={metrics?.runStatus ?? run.manifest.status}
          note={formatDate(run.manifest.updatedAt)}
        />
        <MetricCard
          label="Requests sent"
          value={formatNumber(metrics?.totalRequestsSent)}
          note={`${formatCompactNumber(httpEvents.length)} events in current page`}
        />
        <MetricCard
          label="Successful operations"
          value={formatNumber(metrics?.successfulOperations)}
          note={`${metrics?.successfulPercentage?.toFixed(1) ?? "n/a"}% of spec operations`}
        />
        <MetricCard
          label="Unique server errors"
          value={formatNumber(metrics?.uniqueServerErrors)}
          note={`${formatCompactNumber(fiveXx)} 5xx responses`}
        />
        <MetricCard
          label="Input tokens"
          value={formatNumber(metrics?.inputTokens)}
          note={metrics?.reportSchema ?? "unknown schema"}
        />
        <MetricCard
          label="Output tokens"
          value={formatNumber(metrics?.outputTokens)}
          note={`${formatCompactNumber(metrics?.totalTokens)} total`}
        />
        <MetricCard
          label="Trace events"
          value={formatNumber(metrics?.traceEventCount)}
          note={`${formatCompactNumber(metrics?.checkpointCount)} checkpoints`}
        />
        <MetricCard
          label="4xx / 5xx"
          value={`${formatCompactNumber(fourXx)} / ${formatCompactNumber(fiveXx)}`}
          note={`${formatCompactNumber(logicalEvents.length)} logical requests in current page`}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel title="Status code distribution">
          <ReactECharts
            notMerge
            option={{
              tooltip: { trigger: "item" },
              color: ["#12343b", "#d28b36", "#365f64", "#d35d47", "#8e3b2f"],
              series: [
                {
                  type: "pie",
                  radius: ["42%", "74%"],
                  label: { color: "#12343b" },
                  data: statusSeries,
                  itemStyle: { borderRadius: 10 },
                },
              ],
            }}
            style={{ height: 320 }}
          />
        </Panel>

        <Panel title="Phase activity">
          <ReactECharts
            notMerge
            option={{
              tooltip: { trigger: "axis" },
              legend: { bottom: 0 },
              xAxis: {
                type: "category",
                data: phaseSeries.map((item) => item.phase),
                axisLabel: { rotate: 22 },
              },
              yAxis: { type: "value" },
              color: ["#12343b", "#d28b36", "#5f6f72"],
              series: [
                {
                  name: "Logical",
                  type: "bar",
                  stack: "total",
                  data: phaseSeries.map((item) => item.logical),
                },
                {
                  name: "HTTP",
                  type: "bar",
                  stack: "total",
                  data: phaseSeries.map((item) => item.http),
                },
                {
                  name: "LLM",
                  type: "bar",
                  stack: "total",
                  data: phaseSeries.map((item) => item.llm),
                },
              ],
            }}
            style={{ height: 320 }}
          />
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Panel title="Trace counters">
          <div className="grid gap-3 md:grid-cols-2">
            <AnomalyRow
              label="Logical requests"
              value={formatNumber(metrics?.logicalCount)}
            />
            <AnomalyRow
              label="HTTP attempts"
              value={formatNumber(metrics?.httpAttemptCount)}
            />
            <AnomalyRow
              label="LLM calls"
              value={formatNumber(metrics?.llmCallCount)}
            />
            <AnomalyRow
              label="Snapshot ordering"
              value={timeline?.timelineOrder ?? "n/a"}
            />
          </div>
        </Panel>

        <Panel title="Most expensive operations">
          <div className="space-y-3">
            {topExpensiveOperations.length > 0 ? (
              topExpensiveOperations.map((operation) => (
                <div key={operation.operationId} className="rounded-2xl bg-paper p-4">
                  <div className="font-mono text-xs text-slate">
                    {operation.operationId}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-sm text-ink">
                    <span>{formatCompactNumber(operation.totalTokenCount)} tokens</span>
                    <span>{formatCompactNumber(operation.httpAttemptCount)} HTTP</span>
                    <span>{formatCompactNumber(operation.llmCallCount)} LLM</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-2xl bg-paper p-4 text-sm text-slate">
                Operation metrics are unavailable for this run.
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <Panel className="bg-paper/80">
      <div className="text-xs uppercase tracking-[0.18em] text-slate">{label}</div>
      <div className="mt-2 font-display text-3xl font-semibold text-ink">{value}</div>
      {note ? <div className="mt-1 text-sm text-slate">{note}</div> : null}
    </Panel>
  );
}

function AnomalyRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line bg-paper p-4">
      <div className="text-sm font-medium text-ink">{label}</div>
      <div className="mt-1 text-xl font-semibold text-accent">{value}</div>
    </div>
  );
}
