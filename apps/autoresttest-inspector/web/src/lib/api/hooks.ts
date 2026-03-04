import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { fetchApi } from "@/lib/api/client";
import {
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

export function useGraph(datasetId: string | undefined) {
  return useQuery({
    queryKey: ["graph", datasetId],
    enabled: Boolean(datasetId),
    queryFn: () =>
      fetchApi(`/api/datasets/${datasetId}/graph`, graphSnapshotSchema),
  });
}

export function useRuntimeQtables(datasetId: string | undefined) {
  return useQuery({
    queryKey: ["runtime-qtables", datasetId],
    enabled: Boolean(datasetId),
    queryFn: () =>
      fetchApi(`/api/datasets/${datasetId}/q-tables`, qtableSnapshotSchema),
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

export function useArtifacts(datasetId: string | undefined) {
  return useQuery({
    queryKey: ["artifacts", datasetId],
    enabled: Boolean(datasetId),
    queryFn: () =>
      fetchApi(`/api/datasets/${datasetId}/artifacts`, artifactsResponseSchema),
  });
}

export function useArtifactPayload(
  datasetId: string | undefined,
  artifactName: string | undefined,
) {
  return useQuery({
    queryKey: ["artifact", datasetId, artifactName],
    enabled: Boolean(datasetId && artifactName),
    queryFn: async () => {
      const response = await fetch(
        `/api/datasets/${datasetId}/artifacts/${artifactName}`,
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

type TimelineOptions = {
  enabled?: boolean;
  phase?: string;
  operationId?: string;
  logicalRequestId?: number;
  traceKind?: string;
  statusCode?: number;
  search?: string;
  afterEventSequenceId?: number;
  limit?: number;
  includePayload?: boolean;
  refetchInterval?: number | false;
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
    if (options.search) params.set("search", options.search);
    if (typeof options.afterEventSequenceId === "number") {
      params.set("afterEventSequenceId", String(options.afterEventSequenceId));
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
  phase?: string;
  operationId?: string;
  traceKind?: string;
  statusCode?: number;
  search?: string;
  limit?: number;
};

export function useTraceChains(
  datasetId: string | undefined,
  runId: string | undefined,
  options: TraceChainOptions = {},
) {
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", String(options.limit ?? 100));
    if (options.phase) params.set("phase", options.phase);
    if (options.operationId) params.set("operationId", options.operationId);
    if (options.traceKind) params.set("traceKind", options.traceKind);
    if (typeof options.statusCode === "number") {
      params.set("statusCode", String(options.statusCode));
    }
    if (options.search) params.set("search", options.search);
    return params.toString();
  }, [options]);

  return useQuery({
    queryKey: ["trace-chains", datasetId, runId, queryString],
    enabled: Boolean(datasetId && runId && (options.enabled ?? true)),
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
