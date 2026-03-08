import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { Panel } from "@/components/common/panel";
import { useCompare } from "@/lib/api/hooks";
import { RunManifestSummary } from "@/lib/schemas/api";
import { useInspectorStore } from "@/lib/state/inspector-store";
import { formatCompactNumber, formatNumber } from "@/lib/formatters/format";

type RunComparePanelProps = {
  datasetId: string;
  currentRunId: string;
  runs: RunManifestSummary[];
};

export function RunComparePanel({
  datasetId,
  currentRunId,
  runs,
}: RunComparePanelProps) {
  const baselineRunId = useInspectorStore((state) => state.baselineRunId);
  const candidateRunId = useInspectorStore((state) => state.candidateRunId);
  const setBaselineRunId = useInspectorStore((state) => state.setBaselineRunId);
  const setCandidateRunId = useInspectorStore((state) => state.setCandidateRunId);
  const [operationSearch, setOperationSearch] = useState("");
  const deferredSearch = useDeferredValue(operationSearch);

  useEffect(() => {
    if (!baselineRunId) {
      setBaselineRunId(currentRunId);
    }
    if (!candidateRunId) {
      const alternative = runs.find((run) => run.runId !== currentRunId);
      setCandidateRunId(alternative?.runId ?? currentRunId);
    }
  }, [
    baselineRunId,
    candidateRunId,
    currentRunId,
    runs,
    setBaselineRunId,
    setCandidateRunId,
  ]);

  const compareQuery = useCompare(
    datasetId,
    baselineRunId ?? undefined,
    candidateRunId ?? undefined,
  );

  const filteredOperationDeltas = useMemo(
    () =>
      (compareQuery.data?.operationDeltas ?? []).filter((item) =>
        String(item.operationId ?? "")
          .toLowerCase()
          .includes(deferredSearch.toLowerCase()),
      ),
    [compareQuery.data?.operationDeltas, deferredSearch],
  );

  return (
    <div className="space-y-4">
      <Panel title="Run comparison controls">
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
          <RunSelect
            label="Baseline run"
            value={baselineRunId ?? ""}
            runs={runs}
            onChange={setBaselineRunId}
          />
          <RunSelect
            label="Candidate run"
            value={candidateRunId ?? ""}
            runs={runs}
            onChange={setCandidateRunId}
          />
          <input
            value={operationSearch}
            onChange={(event) => setOperationSearch(event.target.value)}
            placeholder="Filter operation deltas..."
            className="rounded-2xl border border-line bg-paper px-3 py-2 text-sm outline-none"
          />
        </div>
      </Panel>

      <Panel title="Comparison summary">
        {compareQuery.data ? (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <SummaryCard
                label="Request delta"
                value={formatNumber(Number(compareQuery.data.summaryDelta.totalRequests ?? 0))}
              />
              <SummaryCard
                label="Success delta"
                value={formatNumber(Number(compareQuery.data.coverageDelta.delta ?? 0))}
              />
              <SummaryCard
                label="Error delta"
                value={formatNumber(
                  Number(compareQuery.data.summaryDelta.uniqueServerErrors ?? 0),
                )}
              />
              <SummaryCard
                label="Token delta"
                value={formatNumber(Number(compareQuery.data.llmDelta.deltaTokens ?? 0))}
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
              <Panel title="Baseline vs candidate">
                <div className="grid gap-3 md:grid-cols-2">
                  <RunMetaBlock
                    title="Baseline"
                    runId={compareQuery.data.baselineRunId}
                    status={compareQuery.data.baselineMetrics?.runStatus}
                    schema={compareQuery.data.baselineMetrics?.reportSchema}
                    tokens={compareQuery.data.baselineMetrics?.totalTokens}
                    requests={compareQuery.data.baselineMetrics?.totalRequestsSent}
                  />
                  <RunMetaBlock
                    title="Candidate"
                    runId={compareQuery.data.candidateRunId}
                    status={compareQuery.data.candidateMetrics?.runStatus}
                    schema={compareQuery.data.candidateMetrics?.reportSchema}
                    tokens={compareQuery.data.candidateMetrics?.totalTokens}
                    requests={compareQuery.data.candidateMetrics?.totalRequestsSent}
                  />
                </div>
              </Panel>

              <Panel title="Status delta">
                <div className="grid gap-3 md:grid-cols-2">
                  {Object.entries(compareQuery.data.summaryDelta.statusCodes ?? {}).map(
                    ([code, delta]) => (
                      <div key={code} className="rounded-2xl bg-paper p-4">
                        <div className="text-xs uppercase tracking-wide text-slate">
                          {code}
                        </div>
                        <div className="mt-2 text-2xl font-semibold text-ink">
                          {formatNumber(Number(delta))}
                        </div>
                      </div>
                    ),
                  )}
                </div>
              </Panel>
            </div>

            <Panel title="Operation deltas">
              <div className="space-y-3">
                {filteredOperationDeltas.slice(0, 40).map((item) => (
                  <div key={String(item.operationId)} className="rounded-2xl bg-paper p-4">
                    <div className="font-mono text-xs text-slate">
                      {String(item.operationId)}
                    </div>
                    <div className="mt-2 grid gap-3 md:grid-cols-2">
                      <pre className="overflow-auto text-xs text-ink">
                        {JSON.stringify(item.baseline, null, 2)}
                      </pre>
                      <pre className="overflow-auto text-xs text-ink">
                        {JSON.stringify(item.candidate, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
                {!filteredOperationDeltas.length ? (
                  <div className="rounded-2xl bg-paper p-4 text-sm text-slate">
                    No operation delta matches the current filter.
                  </div>
                ) : null}
              </div>
            </Panel>

            <div className="rounded-2xl bg-paper p-4 text-sm text-ink">
              {compareQuery.data.warnings.join(" ") || "No warnings."}
            </div>
          </div>
        ) : (
          <div className="rounded-2xl bg-paper p-4 text-sm text-slate">
            {compareQuery.isLoading ? "Loading comparison..." : "Select two runs to compare."}
          </div>
        )}
      </Panel>
    </div>
  );
}

function RunSelect({
  label,
  value,
  runs,
  onChange,
}: {
  label: string;
  value: string;
  runs: RunManifestSummary[];
  onChange: (value: string | null) => void;
}) {
  return (
    <label className="rounded-2xl bg-paper p-4 text-sm text-ink">
      <div className="text-xs uppercase tracking-wide text-slate">{label}</div>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value || null)}
        className="mt-3 w-full rounded-xl border border-line bg-white px-3 py-2 outline-none"
      >
        {runs.map((run) => (
          <option key={run.runId} value={run.runId}>
            {run.runId}
          </option>
        ))}
      </select>
    </label>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-paper p-4">
      <div className="text-xs uppercase tracking-wide text-slate">{label}</div>
      <div className="mt-2 font-display text-3xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function RunMetaBlock({
  title,
  runId,
  status,
  schema,
  tokens,
  requests,
}: {
  title: string;
  runId: string;
  status?: string;
  schema?: string;
  tokens?: number;
  requests?: number;
}) {
  return (
    <div className="rounded-2xl bg-paper p-4">
      <div className="text-xs uppercase tracking-wide text-slate">{title}</div>
      <div className="mt-2 font-mono text-xs text-ink">{runId}</div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate">
        <span>Status: {status ?? "unknown"}</span>
        <span>Schema: {schema ?? "unknown"}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-sm text-ink">
        <span>{formatCompactNumber(requests)} requests</span>
        <span>{formatCompactNumber(tokens)} tokens</span>
      </div>
    </div>
  );
}
