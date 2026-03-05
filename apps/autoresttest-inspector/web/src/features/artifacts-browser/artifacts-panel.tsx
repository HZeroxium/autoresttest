import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { Panel } from "@/components/common/panel";
import { useArtifactPayload } from "@/lib/api/hooks";
import { ArtifactsResponse } from "@/lib/schemas/api";
import { useInspectorStore } from "@/lib/state/inspector-store";

type ArtifactsPanelProps = {
  datasetId: string;
  runId: string;
  artifacts?: ArtifactsResponse;
};

export function ArtifactsPanel({ datasetId, runId, artifacts }: ArtifactsPanelProps) {
  const selectedArtifact = useInspectorStore((state) => state.selectedArtifact);
  const setSelectedArtifact = useInspectorStore((state) => state.setSelectedArtifact);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    if (!selectedArtifact) {
      const firstAvailable = artifacts?.artifacts.find((artifact) => artifact.available);
      if (firstAvailable) {
        setSelectedArtifact(firstAvailable.name);
      }
    }
  }, [artifacts, selectedArtifact, setSelectedArtifact]);

  const filteredArtifacts = useMemo(
    () =>
      (artifacts?.artifacts ?? []).filter((artifact) =>
        artifact.name.toLowerCase().includes(deferredSearch.toLowerCase()),
      ),
    [artifacts, deferredSearch],
  );

  const payloadQuery = useArtifactPayload(
    datasetId,
    runId,
    selectedArtifact ?? undefined,
  );

  return (
    <div className="grid gap-4 xl:grid-cols-[0.45fr_0.55fr]">
      <Panel
        title="Artifacts"
        actions={
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Filter artifacts..."
            className="rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none"
          />
        }
      >
        <div className="space-y-2">
          {filteredArtifacts.map((artifact) => (
            <button
              key={artifact.name}
              type="button"
              onClick={() => setSelectedArtifact(artifact.name)}
              className={`w-full rounded-2xl border px-3 py-3 text-left text-sm transition-colors ${
                selectedArtifact === artifact.name
                  ? "border-accent bg-accent text-white"
                  : "border-line bg-paper text-ink hover:border-accent"
              }`}
            >
              <div className="font-medium">{artifact.name}</div>
              <div className="mt-1 text-xs opacity-80">
                {artifact.available ? "Available" : "Missing"} | {artifact.itemCount ?? "n/a"} items
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel title={selectedArtifact ?? "Artifact payload"}>
        <pre className="max-h-[560px] overflow-auto rounded-2xl bg-paper p-4 text-xs text-ink">
          {payloadQuery.data
            ? JSON.stringify(payloadQuery.data, null, 2)
            : payloadQuery.isLoading
              ? "Loading..."
              : "Select an artifact to inspect."}
        </pre>
      </Panel>
    </div>
  );
}
