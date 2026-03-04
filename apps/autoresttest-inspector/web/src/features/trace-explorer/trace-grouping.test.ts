import { describe, expect, it } from "vitest";

import { UnifiedTraceEvent } from "@/lib/schemas/api";

import { buildTraceChains, filterTimelineEvents, mergeTimelineEvents } from "./trace-grouping";

function makeEvent(
  overrides: Partial<UnifiedTraceEvent>,
): UnifiedTraceEvent {
  return {
    schemaVersion: 1,
    traceKind: "http_attempt",
    eventSequenceId: 1,
    runId: "run-1",
    phase: "marl_request_generation",
    component: "marl",
    operationId: "GetBill",
    logicalRequestId: 1,
    timestamp: "2026-03-04T15:21:23.000Z",
    durationMs: 10,
    statusCode: 200,
    transportError: null,
    llmPurpose: null,
    cacheHit: null,
    kindLabel: "http attempt",
    summaryLabel: "GET 200",
    statusFamily: "2xx",
    isError: false,
    isRetry: false,
    tokenTotal: null,
    payload: {},
    ...overrides,
  };
}

describe("trace-grouping", () => {
  it("keeps timeline ordering and derives chains by logical request id", () => {
    const events = mergeTimelineEvents(
      [
        makeEvent({
          eventSequenceId: 4,
          traceKind: "logical_request",
          summaryLabel: "logical 2",
          logicalRequestId: 2,
        }),
      ],
      [
        makeEvent({ eventSequenceId: 1, logicalRequestId: 1 }),
        makeEvent({ eventSequenceId: 2, logicalRequestId: 1, traceKind: "llm_call" }),
        makeEvent({
          eventSequenceId: 3,
          logicalRequestId: 1,
          traceKind: "logical_request",
          summaryLabel: "logical 1",
        }),
      ],
    );

    expect(events.map((event) => event.eventSequenceId)).toEqual([1, 2, 3, 4]);

    const chains = buildTraceChains(events);
    expect(chains).toHaveLength(2);
    expect(chains[0]?.logicalRequestId).toBe(1);
    expect(chains[0]?.eventSequenceStart).toBe(1);
    expect(chains[0]?.eventSequenceEnd).toBe(3);
    expect(chains[1]?.logicalRequestId).toBe(2);
  });

  it("filters by phase and retry flag on the flattened timeline", () => {
    const filtered = filterTimelineEvents(
      [
        makeEvent({ eventSequenceId: 10, phase: "value_agent_q_table_generation" }),
        makeEvent({ eventSequenceId: 11, phase: "marl_request_generation", isRetry: true }),
      ],
      {
        search: "",
        operationId: null,
        traceKind: "",
        phases: ["marl_request_generation"],
        errorsOnly: false,
        retriesOnly: true,
        durationRange: [0, 1000],
      },
    );

    expect(filtered.map((event) => event.eventSequenceId)).toEqual([11]);
  });
});
