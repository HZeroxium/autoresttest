import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { fetchApi } from "@/lib/api/client";
import {
  artifactPreviewResponseSchema,
  artifactsResponseSchema,
  cacheQtableSnapshotSchema,
  compareResponseSchema,
  datasetDetailSchema,
  datasetSummarySchema,
  graphSnapshotSchema,
  operationMetricsResponseSchema,
  qtableSnapshotSchema,
  runBundleSummarySchema,
  runManifestSummarySchema,
  traceFacetsResponseSchema,
  traceChainPageSchema,
  timelinePageSchema,
} from "@/lib/schemas/api";

export function useDatasets() {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: () => fetchApi("/api/datasets", z.array(datasetSummarySchema)),
  });
}

export function useDataset(datasetId: string | undefined) {
  return useQuery({
    queryKey: ["dataset", datasetId],
    enabled: Boolean(datasetId),
    queryFn: () => fetchApi(`/api/datasets/${datasetId}`, datasetDetailSchema),
  });
}

export function useRuns(datasetId: string | undefined) {
  return useQuery({
    queryKey: ["runs", datasetId],
    enabled: Boolean(datasetId),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs`,
        z.array(runManifestSummarySchema),
      ),
  });
}

export function useRun(
  datasetId: string | undefined,
  runId: string | undefined,
) {
  return useQuery({
    queryKey: ["run", datasetId, runId],
    enabled: Boolean(datasetId && runId),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}`,
        runBundleSummarySchema,
      ),
  });
}

export function useGraph(
  datasetId: string | undefined,
  runId?: string | undefined,
) {
  return useQuery({
    queryKey: ["graph", datasetId, runId ?? ""],
    enabled: Boolean(datasetId),
    queryFn: () => {
      const query = runId ? `?runId=${encodeURIComponent(runId)}` : "";
      return fetchApi(`/api/datasets/${datasetId}/graph${query}`, graphSnapshotSchema);
    },
  });
}

export function useRuntimeQtables(
  datasetId: string | undefined,
  runId: string | undefined,
) {
  return useQuery({
    queryKey: ["runtime-qtables", datasetId, runId],
    enabled: Boolean(datasetId && runId),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}/q-tables`,
        qtableSnapshotSchema,
      ),
  });
}

export function useCachedQtables(datasetId: string | undefined) {
  return useQuery({
    queryKey: ["cached-qtables", datasetId],
    enabled: Boolean(datasetId),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/cache/q-table`,
        cacheQtableSnapshotSchema,
      ),
  });
}

export function useArtifacts(
  datasetId: string | undefined,
  runId: string | undefined,
) {
  return useQuery({
    queryKey: ["artifacts", datasetId, runId],
    enabled: Boolean(datasetId && runId),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}/artifacts`,
        artifactsResponseSchema,
      ),
  });
}

export function useArtifactPayload(
  datasetId: string | undefined,
  runId: string | undefined,
  artifactName: string | undefined,
) {
  return useQuery({
    queryKey: ["artifact", datasetId, runId, artifactName],
    enabled: Boolean(datasetId && runId && artifactName),
    queryFn: async () => {
      const response = await fetch(
        `/api/datasets/${datasetId}/runs/${runId}/artifacts/${artifactName}`,
      );
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(
          payload?.error?.message ?? `Failed to load artifact ${artifactName}`,
        );
      }
      return response.json() as Promise<Record<string, unknown>>;
    },
  });
}

type ArtifactPreviewOptions = {
  enabled?: boolean;
  offset?: number;
  limit?: number;
  search?: string;
  operationId?: string;
};

export function useArtifactPreview(
  datasetId: string | undefined,
  runId: string | undefined,
  artifactName: string | undefined,
  options: ArtifactPreviewOptions = {},
) {
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("offset", String(options.offset ?? 0));
    params.set("limit", String(options.limit ?? 50));
    if (options.search) params.set("search", options.search);
    if (options.operationId) params.set("operationId", options.operationId);
    return params.toString();
  }, [options]);

  return useQuery({
    queryKey: ["artifact-preview", datasetId, runId, artifactName, queryString],
    enabled: Boolean(datasetId && runId && artifactName && (options.enabled ?? true)),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}/artifacts/${artifactName}/preview?${queryString}`,
        artifactPreviewResponseSchema,
      ),
  });
}

type TimelineOptions = {
  enabled?: boolean;
  phase?: string;
  operationId?: string;
  logicalRequestId?: number;
  traceKind?: string;
  statusCode?: number;
  statusFamily?: string;
  search?: string;
  afterEventSequenceId?: number;
  limit?: number;
  includePayload?: boolean;
  refetchInterval?: number | false;
  cacheHit?: boolean;
  requestFailed?: boolean;
  transportError?: boolean;
  llmPurpose?: string;
  minDurationMs?: number;
  maxDurationMs?: number;
};

export function useTimeline(
  datasetId: string | undefined,
  runId: string | undefined,
  options: TimelineOptions = {},
) {
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", String(options.limit ?? 1000));
    if (options.phase) params.set("phase", options.phase);
    if (options.operationId) params.set("operationId", options.operationId);
    if (typeof options.logicalRequestId === "number") {
      params.set("logicalRequestId", String(options.logicalRequestId));
    }
    if (options.traceKind) params.set("traceKind", options.traceKind);
    if (typeof options.statusCode === "number") {
      params.set("statusCode", String(options.statusCode));
    }
    if (options.statusFamily) params.set("statusFamily", options.statusFamily);
    if (options.search) params.set("search", options.search);
    if (typeof options.afterEventSequenceId === "number") {
      params.set("afterEventSequenceId", String(options.afterEventSequenceId));
    }
    if (typeof options.cacheHit === "boolean") {
      params.set("cacheHit", String(options.cacheHit));
    }
    if (typeof options.requestFailed === "boolean") {
      params.set("requestFailed", String(options.requestFailed));
    }
    if (typeof options.transportError === "boolean") {
      params.set("transportError", String(options.transportError));
    }
    if (options.llmPurpose) params.set("llmPurpose", options.llmPurpose);
    if (typeof options.minDurationMs === "number") {
      params.set("minDurationMs", String(options.minDurationMs));
    }
    if (typeof options.maxDurationMs === "number") {
      params.set("maxDurationMs", String(options.maxDurationMs));
    }
    if (typeof options.includePayload === "boolean") {
      params.set("includePayload", String(options.includePayload));
    }
    return params.toString();
  }, [options]);

  return useQuery({
    queryKey: ["timeline", datasetId, runId, queryString],
    enabled: Boolean(datasetId && runId && (options.enabled ?? true)),
    refetchInterval: options.refetchInterval,
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}/timeline?${queryString}`,
        timelinePageSchema,
      ),
  });
}

type TraceChainOptions = {
  enabled?: boolean;
  afterEventSequenceId?: number;
  phase?: string;
  operationId?: string;
  traceKind?: string;
  statusCode?: number;
  statusFamily?: string;
  search?: string;
  limit?: number;
  cacheHit?: boolean;
  requestFailed?: boolean;
  transportError?: boolean;
  llmPurpose?: string;
  minDurationMs?: number;
  maxDurationMs?: number;
  refetchInterval?: number | false;
};

export function useTraceChains(
  datasetId: string | undefined,
  runId: string | undefined,
  options: TraceChainOptions = {},
) {
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", String(options.limit ?? 100));
    if (typeof options.afterEventSequenceId === "number") {
      params.set("afterEventSequenceId", String(options.afterEventSequenceId));
    }
    if (options.phase) params.set("phase", options.phase);
    if (options.operationId) params.set("operationId", options.operationId);
    if (options.traceKind) params.set("traceKind", options.traceKind);
    if (typeof options.statusCode === "number") {
      params.set("statusCode", String(options.statusCode));
    }
    if (options.statusFamily) params.set("statusFamily", options.statusFamily);
    if (options.search) params.set("search", options.search);
    if (typeof options.cacheHit === "boolean") {
      params.set("cacheHit", String(options.cacheHit));
    }
    if (typeof options.requestFailed === "boolean") {
      params.set("requestFailed", String(options.requestFailed));
    }
    if (typeof options.transportError === "boolean") {
      params.set("transportError", String(options.transportError));
    }
    if (options.llmPurpose) params.set("llmPurpose", options.llmPurpose);
    if (typeof options.minDurationMs === "number") {
      params.set("minDurationMs", String(options.minDurationMs));
    }
    if (typeof options.maxDurationMs === "number") {
      params.set("maxDurationMs", String(options.maxDurationMs));
    }
    return params.toString();
  }, [options]);

  return useQuery({
    queryKey: ["trace-chains", datasetId, runId, queryString],
    enabled: Boolean(datasetId && runId && (options.enabled ?? true)),
    refetchInterval: options.refetchInterval,
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}/trace-chains?${queryString}`,
        traceChainPageSchema,
      ),
  });
}

export function useOperationMetrics(
  datasetId: string | undefined,
  runId: string | undefined,
) {
  return useQuery({
    queryKey: ["operation-metrics", datasetId, runId],
    enabled: Boolean(datasetId && runId),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}/operation-metrics`,
        operationMetricsResponseSchema,
      ),
  });
}

type TraceFacetOptions = {
  enabled?: boolean;
  phase?: string;
  operationId?: string;
  logicalRequestId?: number;
  traceKind?: string;
  statusCode?: number;
  statusFamily?: string;
  search?: string;
  cacheHit?: boolean;
  requestFailed?: boolean;
  transportError?: boolean;
  llmPurpose?: string;
  minDurationMs?: number;
  maxDurationMs?: number;
};

export function useTraceFacets(
  datasetId: string | undefined,
  runId: string | undefined,
  options: TraceFacetOptions = {},
) {
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (options.phase) params.set("phase", options.phase);
    if (options.operationId) params.set("operationId", options.operationId);
    if (typeof options.logicalRequestId === "number") {
      params.set("logicalRequestId", String(options.logicalRequestId));
    }
    if (options.traceKind) params.set("traceKind", options.traceKind);
    if (typeof options.statusCode === "number") {
      params.set("statusCode", String(options.statusCode));
    }
    if (options.statusFamily) params.set("statusFamily", options.statusFamily);
    if (options.search) params.set("search", options.search);
    if (typeof options.cacheHit === "boolean") {
      params.set("cacheHit", String(options.cacheHit));
    }
    if (typeof options.requestFailed === "boolean") {
      params.set("requestFailed", String(options.requestFailed));
    }
    if (typeof options.transportError === "boolean") {
      params.set("transportError", String(options.transportError));
    }
    if (options.llmPurpose) params.set("llmPurpose", options.llmPurpose);
    if (typeof options.minDurationMs === "number") {
      params.set("minDurationMs", String(options.minDurationMs));
    }
    if (typeof options.maxDurationMs === "number") {
      params.set("maxDurationMs", String(options.maxDurationMs));
    }
    return params.toString();
  }, [options]);

  return useQuery({
    queryKey: ["trace-facets", datasetId, runId, queryString],
    enabled: Boolean(datasetId && runId && (options.enabled ?? true)),
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/runs/${runId}/trace-facets?${queryString}`,
        traceFacetsResponseSchema,
      ),
  });
}

export function useCompare(
  datasetId: string | undefined,
  baselineRunId: string | undefined,
  candidateRunId: string | undefined,
) {
  const enabled = Boolean(datasetId && baselineRunId && candidateRunId);
  return useQuery({
    queryKey: ["compare", datasetId, baselineRunId, candidateRunId],
    enabled,
    queryFn: () =>
      fetchApi(
        `/api/datasets/${datasetId}/compare?baselineRunId=${baselineRunId}&candidateRunId=${candidateRunId}`,
        compareResponseSchema,
      ),
  });
}
