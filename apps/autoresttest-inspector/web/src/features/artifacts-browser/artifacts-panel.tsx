import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { Panel } from "@/components/common/panel";
import {
  useArtifactPayload,
  useArtifactPreview,
} from "@/lib/api/hooks";
import { ArtifactsResponse } from "@/lib/schemas/api";
import { formatCompactNumber } from "@/lib/formatters/format";
import { useInspectorStore } from "@/lib/state/inspector-store";

type ArtifactsPanelProps = {
  datasetId: string;
  runId: string;
  artifacts?: ArtifactsResponse;
};

export function ArtifactsPanel({
  datasetId,
  runId,
  artifacts,
}: ArtifactsPanelProps) {
  const selectedArtifact = useInspectorStore((state) => state.selectedArtifact);
  const setSelectedArtifact = useInspectorStore((state) => state.setSelectedArtifact);
  const [search, setSearch] = useState("");
  const [entrySearch, setEntrySearch] = useState("");
  const [operationFilter, setOperationFilter] = useState("");
  const [viewMode, setViewMode] = useState<"preview" | "raw">("preview");
  const deferredSearch = useDeferredValue(search);
  const deferredEntrySearch = useDeferredValue(entrySearch);

  useEffect(() => {
    if (selectedArtifact) {
      return;
    }
    const defaultArtifact =
      artifacts?.artifacts.find((artifact) => artifact.name === "report.json" && artifact.available) ??
      artifacts?.artifacts.find(
        (artifact) => artifact.name === "operation_status_codes.json" && artifact.available,
      ) ??
      artifacts?.artifacts.find((artifact) => artifact.available);
    if (defaultArtifact) {
      setSelectedArtifact(defaultArtifact.name);
    }
  }, [artifacts, selectedArtifact, setSelectedArtifact]);

  const filteredArtifacts = useMemo(
    () =>
      (artifacts?.artifacts ?? []).filter((artifact) =>
        artifact.name.toLowerCase().includes(deferredSearch.toLowerCase()),
      ),
    [artifacts, deferredSearch],
  );

  const previewQuery = useArtifactPreview(
    datasetId,
    runId,
    selectedArtifact ?? undefined,
    {
      enabled: viewMode === "preview" && Boolean(selectedArtifact),
      search: deferredEntrySearch || undefined,
      operationId: operationFilter || undefined,
      limit: 40,
    },
  );

  const payloadQuery = useArtifactPayload(
    datasetId,
    runId,
    viewMode === "raw" ? selectedArtifact ?? undefined : undefined,
  );

  return (
    <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
      <Panel
        title="Artifacts"
        actions={
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Filter artifacts..."
            className="w-full rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none sm:w-auto"
          />
        }
      >
        <div className="space-y-2">
          {filteredArtifacts.map((artifact) => (
            <button
              key={artifact.name}
              type="button"
              onClick={() => {
                setSelectedArtifact(artifact.name);
                setViewMode("preview");
                setEntrySearch("");
                setOperationFilter("");
              }}
              className={`w-full rounded-2xl border px-3 py-3 text-left text-sm transition-colors ${
                selectedArtifact === artifact.name
                  ? "border-accent bg-accent text-white"
                  : "border-line bg-paper text-ink hover:border-accent"
              }`}
            >
              <div className="font-medium">{artifact.name}</div>
              <div className="mt-1 text-xs opacity-80">
                {artifact.available ? "Available" : "Missing"} |{" "}
                {artifact.sizeBytes != null
                  ? `${formatCompactNumber(artifact.sizeBytes)} bytes`
                  : "unknown size"}
              </div>
              <div className="mt-1 text-xs opacity-80">
                Top-level items: {artifact.itemCount ?? "deferred"}
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <div className="space-y-4">
        <Panel
          title={selectedArtifact ?? "Artifact preview"}
          actions={
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setViewMode("preview")}
                className={`rounded-full px-3 py-2 text-sm ${
                  viewMode === "preview"
                    ? "bg-accent text-white"
                    : "border border-line bg-paper text-ink"
                }`}
              >
                Preview
              </button>
              <button
                type="button"
                onClick={() => setViewMode("raw")}
                className={`rounded-full px-3 py-2 text-sm ${
                  viewMode === "raw"
                    ? "bg-accent text-white"
                    : "border border-line bg-paper text-ink"
                }`}
              >
                Raw JSON
              </button>
            </div>
          }
        >
          {viewMode === "preview" ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-[1fr_1fr]">
                <input
                  value={entrySearch}
                  onChange={(event) => setEntrySearch(event.target.value)}
                  placeholder="Search keys..."
                  className="rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none"
                />
                <input
                  value={operationFilter}
                  onChange={(event) => setOperationFilter(event.target.value)}
                  placeholder="Exact operation key..."
                  className="rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none"
                />
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <InfoTile
                  label="Top-level type"
                  value={String(previewQuery.data?.summary.topLevelType ?? "n/a")}
                />
                <InfoTile
                  label="Total items"
                  value={formatCompactNumber(
                    Number(previewQuery.data?.summary.totalItems ?? 0),
                  )}
                />
                <InfoTile
                  label="Preview entries"
                  value={formatCompactNumber(previewQuery.data?.entries.length)}
                />
              </div>

              {previewQuery.data?.warnings.length ? (
                <div className="rounded-2xl border border-line bg-paper p-4 text-sm text-slate">
                  {previewQuery.data.warnings.join(" ")}
                </div>
              ) : null}

              <div className="space-y-3">
                {previewQuery.data?.entries.map((entry) => (
                  <div key={entry.key} className="rounded-2xl bg-paper p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="font-mono text-xs text-slate">{entry.key}</div>
                      <div className="text-xs uppercase tracking-wide text-slate">
                        {entry.valueType}
                        {entry.itemCount != null ? ` | ${entry.itemCount} items` : ""}
                      </div>
                    </div>
                    <pre className="mt-2 overflow-auto text-xs text-ink">
                      {JSON.stringify(entry.preview, null, 2)}
                    </pre>
                  </div>
                ))}
                {previewQuery.isLoading ? (
                  <div className="rounded-2xl bg-paper p-4 text-sm text-slate">
                    Loading artifact preview...
                  </div>
                ) : null}
                {!previewQuery.isLoading && !previewQuery.data?.entries.length ? (
                  <div className="rounded-2xl bg-paper p-4 text-sm text-slate">
                    No preview entries match the current filters.
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <pre className="max-h-[640px] overflow-auto rounded-2xl bg-paper p-4 text-xs text-ink">
              {payloadQuery.data
                ? JSON.stringify(payloadQuery.data, null, 2)
                : payloadQuery.isLoading
                  ? "Loading raw artifact..."
                  : "Select an artifact to inspect."}
            </pre>
          )}
        </Panel>
      </div>
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-paper p-4">
      <div className="text-xs uppercase tracking-wide text-slate">{label}</div>
      <div className="mt-2 text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}
