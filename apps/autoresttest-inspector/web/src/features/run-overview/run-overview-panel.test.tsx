import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RunOverviewPanel } from "@/features/run-overview/run-overview-panel";
import {
  OperationMetricsResponse,
  RunBundleSummary,
  TimelinePage,
} from "@/lib/schemas/api";

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="echarts-panel" />,
}));

describe("RunOverviewPanel", () => {
  it("renders token metrics, warnings, and expensive operations", () => {
    const run: RunBundleSummary = {
      manifest: {
        runId: "demo-20260305T000000Z-1000",
        datasetId: "demo",
        status: "completed",
        startedAt: "2026-03-05T00:00:00Z",
        updatedAt: "2026-03-05T00:00:10Z",
        completedAt: "2026-03-05T00:00:11Z",
        paths: {},
        counters: {},
        traceAvailability: {},
      },
      report: null,
      reportMetrics: {
        title: "Legacy run",
        durationSeconds: 11,
        runStatus: "completed",
        snapshotReason: "checkpoint_saved",
        totalRequestsSent: 8,
        statusCodeDistribution: { "200": 5, "404": 2, "500": 1 },
        totalOperations: 4,
        successfulOperations: 3,
        successfulPercentage: 75,
        uniqueServerErrors: 1,
        inputTokens: 120,
        outputTokens: 45,
        totalTokens: 165,
        traceEventCount: 22,
        logicalCount: 6,
        httpAttemptCount: 8,
        llmCallCount: 5,
        checkpointCount: 2,
        reportSchema: "legacy_report",
        derivedFields: ["runStatus", "totalTokens"],
      },
      operationStatusCodes: { opA: { "200": 2 } },
      hasQtableSnapshot: true,
      traceCounts: { logical_requests: 6, http_attempts: 8, llm_calls: 5 },
      phaseSummaries: {
        exploration: { logical_request: 6, http_attempt: 8, llm_call: 5 },
      },
      warnings: [],
    };
    const timeline: TimelinePage = {
      runId: "demo-20260305T000000Z-1000",
      cursor: 8,
      events: [
        {
          schemaVersion: 1,
          traceKind: "logical_request",
          eventSequenceId: 1,
          runId: "demo-20260305T000000Z-1000",
          phase: "exploration",
          component: "value_agent",
          operationId: "opA",
          logicalRequestId: 1,
          timestamp: "2026-03-05T00:00:01Z",
          durationMs: 100,
          statusCode: null,
          transportError: null,
          llmPurpose: null,
          cacheHit: null,
          kindLabel: "Logical request",
          summaryLabel: "logical",
          statusFamily: null,
          isError: false,
          isRetry: false,
          tokenTotal: null,
          payload: {},
        },
        {
          schemaVersion: 1,
          traceKind: "http_attempt",
          eventSequenceId: 2,
          runId: "demo-20260305T000000Z-1000",
          phase: "exploration",
          component: "value_agent",
          operationId: "opA",
          logicalRequestId: 1,
          timestamp: "2026-03-05T00:00:01Z",
          durationMs: 20,
          statusCode: 500,
          transportError: null,
          llmPurpose: null,
          cacheHit: null,
          kindLabel: "HTTP attempt",
          summaryLabel: "http",
          statusFamily: "5xx",
          isError: true,
          isRetry: false,
          tokenTotal: null,
          payload: {},
        },
      ],
      hasMore: false,
      timelineOrder: "native",
      isLiveCapable: true,
      warnings: [],
    };
    const operationMetrics: OperationMetricsResponse = {
      runId: "demo-20260305T000000Z-1000",
      operations: [
        {
          operationId: "opA",
          logicalCount: 2,
          httpAttemptCount: 3,
          llmCallCount: 2,
          retryCount: 0,
          success2xxCount: 2,
          clientError4xxCount: 0,
          serverError5xxCount: 1,
          transportErrorCount: 0,
          avgDurationMs: 45,
          maxDurationMs: 100,
          inputTokenTotal: 100,
          outputTokenTotal: 40,
          totalTokenCount: 140,
          statusCodeBreakdown: { "200": 2, "500": 1 },
        },
      ],
      totals: {
        operationCount: 1,
        inputTokenTotal: 100,
        outputTokenTotal: 40,
        tokenTotal: 140,
      },
      warnings: [],
    };

    render(
      <RunOverviewPanel
        run={run}
        timeline={timeline}
        operationMetrics={operationMetrics}
      />,
    );

    expect(
      screen.getByText(/This run uses a legacy report schema/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Input tokens")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("Most expensive operations")).toBeInTheDocument();
    expect(screen.getByText("opA")).toBeInTheDocument();
    expect(screen.getByText("140 tokens")).toBeInTheDocument();
  });
});
