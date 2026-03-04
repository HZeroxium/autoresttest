import { TraceChainItem, TraceChainSummary, UnifiedTraceEvent } from "@/lib/schemas/api";

function chainIdForEvent(event: UnifiedTraceEvent) {
  if (typeof event.logicalRequestId === "number") {
    return `logical:${event.logicalRequestId}`;
  }
  return `orphan:${event.traceKind}:${event.eventSequenceId}`;
}

export function toTraceChainItem(event: UnifiedTraceEvent): TraceChainItem {
  return {
    eventSequenceId: event.eventSequenceId,
    traceKind: event.traceKind,
    timestamp: event.timestamp,
    durationMs: event.durationMs,
    statusCode: event.statusCode,
    isError: Boolean(event.isError),
    isRetry: Boolean(event.isRetry),
    summaryLabel: event.summaryLabel ?? event.kindLabel ?? event.traceKind,
    operationId: event.operationId ?? null,
    logicalRequestId: event.logicalRequestId ?? null,
  };
}

function buildChainFromEvent(event: UnifiedTraceEvent): TraceChainSummary {
  const item = toTraceChainItem(event);
  return {
    chainId: chainIdForEvent(event),
    logicalRequestId: event.logicalRequestId ?? null,
    isOrphan: event.logicalRequestId == null,
    phase: event.phase ?? null,
    component: event.component ?? null,
    operationId: event.operationId ?? null,
    startedAt: event.timestamp ?? null,
    completedAt: event.timestamp ?? null,
    durationMs: event.traceKind === "logical_request" ? event.durationMs ?? null : null,
    eventSequenceStart: event.eventSequenceId,
    eventSequenceEnd: event.eventSequenceId,
    httpAttemptCount: event.traceKind === "http_attempt" ? 1 : 0,
    llmCallCount: event.traceKind === "llm_call" ? 1 : 0,
    hasError: Boolean(event.isError),
    hasRetry: Boolean(event.isRetry),
    hasCacheHit: Boolean(event.cacheHit),
    dominantStatusCode: event.statusCode ?? null,
    items: [item],
  };
}

export function mergeTimelineIntoChains(
  chains: TraceChainSummary[],
  incomingEvents: UnifiedTraceEvent[],
) {
  if (incomingEvents.length === 0) {
    return chains;
  }

  const nextChains = [...chains];
  const chainIndex = new Map(nextChains.map((chain, index) => [chain.chainId, index]));

  for (const event of incomingEvents) {
    const chainId = chainIdForEvent(event);
    const index = chainIndex.get(chainId);
    if (index === undefined) {
      nextChains.push(buildChainFromEvent(event));
      chainIndex.set(chainId, nextChains.length - 1);
      continue;
    }

    const chain = nextChains[index];
    if (chain.items.some((item) => item.eventSequenceId === event.eventSequenceId)) {
      continue;
    }

    const nextItem = toTraceChainItem(event);
    const nextItems = [...chain.items, nextItem].sort(
      (left, right) => left.eventSequenceId - right.eventSequenceId,
    );
    nextChains[index] = {
      ...chain,
      items: nextItems,
      phase: chain.phase ?? event.phase ?? null,
      component: chain.component ?? event.component ?? null,
      operationId: chain.operationId ?? event.operationId ?? null,
      startedAt: chain.startedAt ?? event.timestamp ?? null,
      completedAt: event.timestamp ?? chain.completedAt ?? null,
      eventSequenceStart: Math.min(chain.eventSequenceStart, event.eventSequenceId),
      eventSequenceEnd: Math.max(chain.eventSequenceEnd, event.eventSequenceId),
      httpAttemptCount:
        chain.httpAttemptCount + (event.traceKind === "http_attempt" ? 1 : 0),
      llmCallCount: chain.llmCallCount + (event.traceKind === "llm_call" ? 1 : 0),
      hasError: chain.hasError || Boolean(event.isError),
      hasRetry: chain.hasRetry || Boolean(event.isRetry),
      hasCacheHit: chain.hasCacheHit || Boolean(event.cacheHit),
      dominantStatusCode: chain.dominantStatusCode ?? event.statusCode ?? null,
    };
  }

  return nextChains.sort(
    (left, right) => left.eventSequenceStart - right.eventSequenceStart,
  );
}
