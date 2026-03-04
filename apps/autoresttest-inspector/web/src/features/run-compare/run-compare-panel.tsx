import { useEffect } from "react";

import { Panel } from "@/components/common/panel";
import { useCompare } from "@/lib/api/hooks";
import { RunManifestSummary } from "@/lib/schemas/api";
import { useInspectorStore } from "@/lib/state/inspector-store";
import { formatNumber } from "@/lib/formatters/format";

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

  return (
    <div className="space-y-4">
      <Panel title="Run comparison controls">
        <div className="grid gap-3 md:grid-cols-2">
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
        </div>
      </Panel>

      <Panel title="Comparison summary">
        {compareQuery.data ? (
          <div className="grid gap-3 md:grid-cols-3">
            <SummaryCard
              label="Request delta"
              value={formatNumber(Number(compareQuery.data.summaryDelta.totalRequests ?? 0))}
            />
            <SummaryCard
              label="Success delta"
              value={formatNumber(Number(compareQuery.data.coverageDelta.delta ?? 0))}
            />
            <SummaryCard
              label="LLM delta"
              value={formatNumber(Number(compareQuery.data.llmDelta.deltaCalls ?? 0))}
            />
            <div className="md:col-span-3 rounded-2xl bg-paper p-4">
              <div className="text-xs uppercase tracking-wide text-slate">Warnings</div>
              <div className="mt-2 text-sm text-ink">
                {compareQuery.data.warnings.join(" ") || "No warnings."}
              </div>
            </div>
            <div className="md:col-span-3 rounded-2xl bg-paper p-4">
              <div className="text-xs uppercase tracking-wide text-slate">
                Operation deltas
              </div>
              <pre className="mt-2 max-h-[280px] overflow-auto text-xs text-ink">
                {JSON.stringify(compareQuery.data.operationDeltas, null, 2)}
              </pre>
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
      <div className="mt-2 font-display text-2xl font-semibold text-ink">{value}</div>
    </div>
  );
}
