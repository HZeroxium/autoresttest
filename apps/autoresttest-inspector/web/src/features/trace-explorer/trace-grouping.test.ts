import { describe, expect, it } from "vitest";

import { TraceChainSummary, UnifiedTraceEvent } from "@/lib/schemas/api";

import { mergeTimelineIntoChains } from "./trace-grouping";

function buildEvent(
  overrides: Partial<UnifiedTraceEvent>,
): UnifiedTraceEvent {
  return {
    schemaVersion: 1,
    traceKind: "http_attempt",
    eventSequenceId: 1,
    runId: "run-1",
    phase: "marl",
    component: "tester",
    operationId: "GetBill",
    logicalRequestId: 1,
    timestamp: "2026-03-04T15:28:05.658029Z",
    durationMs: 120,
    statusCode: 200,
    transportError: null,
    llmPurpose: null,
    cacheHit: null,
    kindLabel: "HTTP attempt",
    summaryLabel: "GET 200",
    statusFamily: "2xx",
    isError: false,
    isRetry: false,
    tokenTotal: null,
    payload: {},
    ...overrides,
  };
}

describe("mergeTimelineIntoChains", () => {
  it("creates and appends chain items by logical request id", () => {
    const initial: TraceChainSummary[] = [];
    const firstPass = mergeTimelineIntoChains(initial, [buildEvent({})]);
    expect(firstPass).toHaveLength(1);
    expect(firstPass[0].items).toHaveLength(1);

    const secondPass = mergeTimelineIntoChains(firstPass, [
      buildEvent({
        eventSequenceId: 2,
        traceKind: "llm_call",
        summaryLabel: "value_agent • live",
        llmPurpose: "value_agent_params",
      }),
    ]);
    expect(secondPass).toHaveLength(1);
    expect(secondPass[0].items).toHaveLength(2);
    expect(secondPass[0].llmCallCount).toBe(1);
  });
});
