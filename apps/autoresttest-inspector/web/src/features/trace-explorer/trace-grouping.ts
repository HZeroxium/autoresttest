import {
  TraceChainItem,
  TraceChainSummary,
  UnifiedTraceEvent,
} from "@/lib/schemas/api";

export type TraceViewMode =
  | "story"
  | "swimlanes"
  | "ribbon"
  | "cards"
  | "ledger";

export type TraceExplorerFilters = {
  search: string;
  operationId: string | null;
  traceKind: string;
  phases: string[];
  errorsOnly: boolean;
  retriesOnly: boolean;
  durationRange: [number, number];
};

export function chainIdForEvent(event: UnifiedTraceEvent) {
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

function buildChainFromEvents(events: UnifiedTraceEvent[]): TraceChainSummary {
  const sortedEvents = [...events].sort(
    (left, right) => left.eventSequenceId - right.eventSequenceId,
  );
  const headerEvent =
    sortedEvents.find((event) => event.traceKind === "logical_request") ??
    sortedEvents[0];

  const httpEvents = sortedEvents.filter((event) => event.traceKind === "http_attempt");
  const llmEvents = sortedEvents.filter((event) => event.traceKind === "llm_call");

  const dominantStatusCode = (() => {
    const counts = new Map<number, number>();
    for (const event of httpEvents) {
      if (typeof event.statusCode !== "number") {
        continue;
      }
      counts.set(event.statusCode, (counts.get(event.statusCode) ?? 0) + 1);
    }
    const top = [...counts.entries()].sort(
      (left, right) => right[1] - left[1] || left[0] - right[0],
    )[0];
    return top?.[0] ?? null;
  })();

  return {
    chainId: chainIdForEvent(headerEvent),
    logicalRequestId: headerEvent.logicalRequestId ?? null,
    isOrphan: headerEvent.logicalRequestId == null,
    phase: headerEvent.phase ?? null,
    component: headerEvent.component ?? null,
    operationId: headerEvent.operationId ?? null,
    startedAt:
      (sortedEvents.find((event) => event.traceKind === "logical_request")?.payload
        ?.started_at as string | undefined) ??
      headerEvent.timestamp ??
      null,
    completedAt:
      (sortedEvents.find((event) => event.traceKind === "logical_request")?.payload
        ?.completed_at as string | undefined) ??
      sortedEvents[sortedEvents.length - 1]?.timestamp ??
      null,
    durationMs:
      sortedEvents.find((event) => event.traceKind === "logical_request")?.durationMs ??
      headerEvent.durationMs ??
      null,
    eventSequenceStart: sortedEvents[0]?.eventSequenceId ?? 0,
    eventSequenceEnd: sortedEvents[sortedEvents.length - 1]?.eventSequenceId ?? 0,
    httpAttemptCount: httpEvents.length,
    llmCallCount: llmEvents.length,
    hasError: sortedEvents.some((event) => Boolean(event.isError)),
    hasRetry: sortedEvents.some((event) => Boolean(event.isRetry)),
    hasCacheHit: llmEvents.some((event) => Boolean(event.cacheHit)),
    dominantStatusCode,
    items: sortedEvents.map(toTraceChainItem),
  };
}

export function mergeTimelineEvents(
  currentEvents: UnifiedTraceEvent[],
  incomingEvents: UnifiedTraceEvent[],
) {
  if (incomingEvents.length === 0) {
    return currentEvents;
  }

  const merged = new Map<number, UnifiedTraceEvent>();
  for (const event of currentEvents) {
    merged.set(event.eventSequenceId, event);
  }
  for (const event of incomingEvents) {
    merged.set(event.eventSequenceId, event);
  }

  return [...merged.values()].sort(
    (left, right) => left.eventSequenceId - right.eventSequenceId,
  );
}

export function filterTimelineEvents(
  events: UnifiedTraceEvent[],
  filters: TraceExplorerFilters,
) {
  const loweredSearch = filters.search.trim().toLowerCase();

  return events.filter((event) => {
    if (filters.operationId && event.operationId !== filters.operationId) {
      return false;
    }
    if (filters.traceKind && event.traceKind !== filters.traceKind) {
      return false;
    }
    if (
      filters.phases.length > 0 &&
      (!event.phase || !filters.phases.includes(event.phase))
    ) {
      return false;
    }
    const eventDuration = event.durationMs ?? 0;
    if (
      eventDuration < filters.durationRange[0] ||
      eventDuration > filters.durationRange[1]
    ) {
      return false;
    }
    if (filters.errorsOnly && !event.isError) {
      return false;
    }
    if (filters.retriesOnly && !event.isRetry) {
      return false;
    }
    if (!loweredSearch) {
      return true;
    }

    const haystack = JSON.stringify({
      summaryLabel: event.summaryLabel,
      operationId: event.operationId,
      phase: event.phase,
      payload: event.payload,
    }).toLowerCase();
    return haystack.includes(loweredSearch);
  });
}

export function buildTraceChains(events: UnifiedTraceEvent[]) {
  const grouped = new Map<string, UnifiedTraceEvent[]>();
  for (const event of events) {
    const chainId = chainIdForEvent(event);
    const current = grouped.get(chainId) ?? [];
    current.push(event);
    grouped.set(chainId, current);
  }

  return [...grouped.values()]
    .map((groupEvents) => buildChainFromEvents(groupEvents))
    .sort((left, right) => left.eventSequenceStart - right.eventSequenceStart);
}

export function groupChainsByPhase(chains: TraceChainSummary[]) {
  const sections: Array<{ phase: string; chains: TraceChainSummary[] }> = [];
  const lookup = new Map<string, { phase: string; chains: TraceChainSummary[] }>();

  for (const chain of chains) {
    const phase = chain.phase ?? "unknown";
    let section = lookup.get(phase);
    if (!section) {
      section = { phase, chains: [] };
      lookup.set(phase, section);
      sections.push(section);
    }
    section.chains.push(chain);
  }

  return sections;
}

export function getEventBySequence(
  events: UnifiedTraceEvent[],
  eventSequenceId: number | null,
) {
  if (eventSequenceId == null) {
    return undefined;
  }
  return events.find((event) => event.eventSequenceId === eventSequenceId);
}

export function mergeTimelineIntoChains(
  chains: TraceChainSummary[],
  incomingEvents: UnifiedTraceEvent[],
) {
  const currentEvents = chains.flatMap((chain) =>
    chain.items.map(
      (item) =>
        ({
          schemaVersion: 0,
          traceKind: item.traceKind,
          eventSequenceId: item.eventSequenceId,
          runId: "",
          phase: chain.phase ?? null,
          component: chain.component ?? null,
          operationId: item.operationId ?? chain.operationId ?? null,
          logicalRequestId: item.logicalRequestId ?? chain.logicalRequestId ?? null,
          timestamp: item.timestamp ?? null,
          durationMs: item.durationMs ?? null,
          statusCode: item.statusCode ?? null,
          transportError: null,
          llmPurpose: null,
          cacheHit: chain.hasCacheHit,
          kindLabel: item.traceKind,
          summaryLabel: item.summaryLabel,
          statusFamily:
            typeof item.statusCode === "number"
              ? `${Math.floor(item.statusCode / 100)}xx`
              : null,
          isError: item.isError,
          isRetry: item.isRetry,
          tokenTotal: null,
          payload: {},
        }) satisfies UnifiedTraceEvent,
    ),
  );
  return buildTraceChains(mergeTimelineEvents(currentEvents, incomingEvents));
}
