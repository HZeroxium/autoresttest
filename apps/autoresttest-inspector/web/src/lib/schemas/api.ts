import { z } from "zod";

export const datasetSummarySchema = z.object({
  datasetId: z.string(),
  displayName: z.string(),
  hasDataArtifacts: z.boolean(),
  hasRuntimeManifests: z.boolean(),
  hasTraceArtifacts: z.boolean(),
  hasGraphCache: z.boolean(),
  hasQtableCache: z.boolean(),
  latestRunId: z.string().nullable().optional(),
  latestRunStatus: z.string().nullable().optional(),
  latestUpdatedAt: z.string().datetime().nullable().optional(),
});

export const runManifestSummarySchema = z.object({
  runId: z.string(),
  datasetId: z.string(),
  status: z.string(),
  startedAt: z.string().datetime().nullable().optional(),
  updatedAt: z.string().datetime().nullable().optional(),
  completedAt: z.string().datetime().nullable().optional(),
  paths: z.record(z.any()),
  counters: z.record(z.any()),
  traceAvailability: z.record(z.boolean()),
});

export const datasetDetailSchema = z.object({
  dataset: datasetSummarySchema,
  latestRun: runManifestSummarySchema.nullable().optional(),
  reportSummary: z.record(z.any()).nullable().optional(),
  runCount: z.number(),
  traceFileCount: z.number(),
  artifactNames: z.array(z.string()),
  hasGraphCache: z.boolean(),
  hasQtableCache: z.boolean(),
  warnings: z.array(z.string()),
});

export const graphNodeSchema = z.object({
  id: z.string(),
  label: z.string(),
  method: z.string(),
  path: z.string(),
  resourceGroup: z.string(),
  summary: z.string().nullable().optional(),
  parameterCount: z.number(),
  requiredParameterCount: z.number(),
  requestBodyMimeTypes: z.array(z.string()),
  responseStatuses: z.array(z.string()),
  hasRuntimeQtable: z.boolean(),
  hasCachedValueQtable: z.boolean(),
  inDegree: z.number(),
  outDegree: z.number(),
  totalDegree: z.number(),
});

export const graphEdgeSchema = z.object({
  id: z.string(),
  sourceId: z.string(),
  targetId: z.string(),
  layer: z.string(),
  isEffective: z.boolean(),
  similarityLinks: z.array(z.record(z.any())),
  maxSimilarity: z.number(),
  linkCount: z.number(),
});

export const graphSnapshotSchema = z.object({
  datasetId: z.string(),
  nodeCount: z.number(),
  edgeCount: z.number(),
  nodes: z.array(graphNodeSchema),
  edges: z.array(graphEdgeSchema),
  warnings: z.array(z.string()),
});

export const qtableAgentSummarySchema = z.object({
  agentName: z.string(),
  entryCount: z.number(),
  nonZeroCount: z.number(),
  minValue: z.number().nullable().optional(),
  maxValue: z.number().nullable().optional(),
  meanValue: z.number().nullable().optional(),
  sparsityRatio: z.number(),
});

export const qtableSnapshotSchema = z.object({
  datasetId: z.string(),
  runtimeQtables: z.record(z.any()),
  agentSummaries: z.array(qtableAgentSummarySchema),
  operations: z.record(z.any()),
  warnings: z.array(z.string()),
});

export const cacheQtableSnapshotSchema = z.object({
  datasetId: z.string(),
  valueAgent: z.record(z.any()),
  headerAgent: z.record(z.any()),
  warnings: z.array(z.string()),
});

export const unifiedTraceEventSchema = z.object({
  schemaVersion: z.number(),
  traceKind: z.string(),
  eventSequenceId: z.number(),
  runId: z.string(),
  phase: z.string().nullable().optional(),
  component: z.string().nullable().optional(),
  operationId: z.string().nullable().optional(),
  logicalRequestId: z.number().nullable().optional(),
  timestamp: z.string().datetime().nullable().optional(),
  durationMs: z.number().nullable().optional(),
  statusCode: z.number().nullable().optional(),
  transportError: z.record(z.any()).nullable().optional(),
  llmPurpose: z.string().nullable().optional(),
  cacheHit: z.boolean().nullable().optional(),
  kindLabel: z.string().nullable().optional(),
  summaryLabel: z.string().nullable().optional(),
  statusFamily: z.string().nullable().optional(),
  isError: z.boolean().nullable().optional(),
  isRetry: z.boolean().nullable().optional(),
  tokenTotal: z.number().nullable().optional(),
  payload: z.record(z.any()),
});

export const timelinePageSchema = z.object({
  runId: z.string(),
  cursor: z.number(),
  events: z.array(unifiedTraceEventSchema),
  hasMore: z.boolean(),
  timelineOrder: z.string(),
  isLiveCapable: z.boolean(),
  warnings: z.array(z.string()),
});

export const traceChainItemSchema = z.object({
  eventSequenceId: z.number(),
  traceKind: z.string(),
  timestamp: z.string().datetime().nullable().optional(),
  durationMs: z.number().nullable().optional(),
  statusCode: z.number().nullable().optional(),
  isError: z.boolean(),
  isRetry: z.boolean(),
  summaryLabel: z.string(),
  operationId: z.string().nullable().optional(),
  logicalRequestId: z.number().nullable().optional(),
});

export const traceChainSummarySchema = z.object({
  chainId: z.string(),
  logicalRequestId: z.number().nullable().optional(),
  isOrphan: z.boolean(),
  phase: z.string().nullable().optional(),
  component: z.string().nullable().optional(),
  operationId: z.string().nullable().optional(),
  startedAt: z.string().datetime().nullable().optional(),
  completedAt: z.string().datetime().nullable().optional(),
  durationMs: z.number().nullable().optional(),
  eventSequenceStart: z.number(),
  eventSequenceEnd: z.number(),
  httpAttemptCount: z.number(),
  llmCallCount: z.number(),
  hasError: z.boolean(),
  hasRetry: z.boolean(),
  hasCacheHit: z.boolean(),
  dominantStatusCode: z.number().nullable().optional(),
  items: z.array(traceChainItemSchema),
});

export const traceChainPageSchema = z.object({
  runId: z.string(),
  cursor: z.number(),
  chains: z.array(traceChainSummarySchema),
  hasMore: z.boolean(),
  warnings: z.array(z.string()),
});

export const operationMetricSchema = z.object({
  operationId: z.string(),
  logicalCount: z.number(),
  httpAttemptCount: z.number(),
  llmCallCount: z.number(),
  retryCount: z.number(),
  success2xxCount: z.number(),
  clientError4xxCount: z.number(),
  serverError5xxCount: z.number(),
  transportErrorCount: z.number(),
  avgDurationMs: z.number().nullable().optional(),
  maxDurationMs: z.number().nullable().optional(),
});

export const operationMetricsResponseSchema = z.object({
  runId: z.string(),
  operations: z.array(operationMetricSchema),
  totals: z.record(z.any()),
  warnings: z.array(z.string()),
});

export const artifactsResponseSchema = z.object({
  datasetId: z.string(),
  artifacts: z.array(
    z.object({
      name: z.string(),
      available: z.boolean(),
      sizeBytes: z.number().nullable().optional(),
      itemCount: z.number().nullable().optional(),
    }),
  ),
});

export const runBundleSummarySchema = z.object({
  manifest: runManifestSummarySchema,
  report: z.record(z.any()).nullable().optional(),
  operationStatusCodes: z.record(z.record(z.number())).nullable().optional(),
  traceCounts: z.record(z.number()),
  phaseSummaries: z.record(z.record(z.number())),
  warnings: z.array(z.string()),
});

export const compareResponseSchema = z.object({
  datasetId: z.string(),
  baselineRunId: z.string(),
  candidateRunId: z.string(),
  summaryDelta: z.record(z.any()),
  coverageDelta: z.record(z.any()),
  traceVolumeDelta: z.record(z.any()),
  llmDelta: z.record(z.any()),
  operationDeltas: z.array(z.record(z.any())),
  qtableComparisonAvailable: z.boolean(),
  warnings: z.array(z.string()),
});

export type DatasetSummary = z.infer<typeof datasetSummarySchema>;
export type DatasetDetail = z.infer<typeof datasetDetailSchema>;
export type RunManifestSummary = z.infer<typeof runManifestSummarySchema>;
export type RunBundleSummary = z.infer<typeof runBundleSummarySchema>;
export type GraphNode = z.infer<typeof graphNodeSchema>;
export type GraphEdge = z.infer<typeof graphEdgeSchema>;
export type GraphSnapshot = z.infer<typeof graphSnapshotSchema>;
export type QTableSnapshot = z.infer<typeof qtableSnapshotSchema>;
export type CacheQTableSnapshot = z.infer<typeof cacheQtableSnapshotSchema>;
export type TimelinePage = z.infer<typeof timelinePageSchema>;
export type UnifiedTraceEvent = z.infer<typeof unifiedTraceEventSchema>;
export type TraceChainItem = z.infer<typeof traceChainItemSchema>;
export type TraceChainSummary = z.infer<typeof traceChainSummarySchema>;
export type TraceChainPage = z.infer<typeof traceChainPageSchema>;
export type OperationMetric = z.infer<typeof operationMetricSchema>;
export type OperationMetricsResponse = z.infer<
  typeof operationMetricsResponseSchema
>;
export type ArtifactsResponse = z.infer<typeof artifactsResponseSchema>;
export type CompareResponse = z.infer<typeof compareResponseSchema>;
