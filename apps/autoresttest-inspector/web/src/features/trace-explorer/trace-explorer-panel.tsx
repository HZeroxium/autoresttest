import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Alert, Button, Chip, Stack } from "@mui/material";

import { Panel } from "@/components/common/panel";
import {
  useTimeline,
  useTraceChains,
  useTraceFacets,
} from "@/lib/api/hooks";
import { TraceChainSummary, UnifiedTraceEvent } from "@/lib/schemas/api";
import { useInspectorStore } from "@/lib/state/inspector-store";

import { TraceChainBoard } from "./trace-chain-board";
import { TraceDensityStrip } from "./trace-density-strip";
import { TraceDetailDrawer } from "./trace-detail-drawer";
import { TraceLedger } from "./trace-ledger";
import { TracePhaseSwimlanes } from "./trace-phase-swimlanes";
import { TraceSequenceRibbon } from "./trace-sequence-ribbon";
import { TraceSequenceStory } from "./trace-sequence-story";
import {
  TraceViewMode,
  buildTraceChains,
  getEventBySequence,
  mergeTimelineEvents,
} from "./trace-grouping";
import { TraceViewControls } from "./trace-view-controls";

type TraceExplorerPanelProps = {
  datasetId: string;
  runId: string;
  runStatus: string;
};

type TriState = "all" | "true" | "false";

function triStateToBoolean(value: TriState): boolean | undefined {
  if (value === "all") {
    return undefined;
  }
  return value === "true";
}

function mergeTraceChains(
  currentChains: TraceChainSummary[],
  incomingChains: TraceChainSummary[],
) {
  if (incomingChains.length === 0) {
    return currentChains;
  }
  const merged = new Map<string, TraceChainSummary>();
  for (const chain of currentChains) {
    merged.set(chain.chainId, chain);
  }
  for (const chain of incomingChains) {
    merged.set(chain.chainId, chain);
  }
  return [...merged.values()].sort(
    (left, right) => left.eventSequenceStart - right.eventSequenceStart,
  );
}

export function TraceExplorerPanel({
  datasetId,
  runId,
  runStatus,
}: TraceExplorerPanelProps) {
  const traceSearch = useInspectorStore((state) => state.traceSearch);
  const setTraceSearch = useInspectorStore((state) => state.setTraceSearch);
  const selectedOperationId = useInspectorStore((state) => state.selectedOperationId);
  const setSelectedOperationId = useInspectorStore(
    (state) => state.setSelectedOperationId,
  );
  const liveMode = useInspectorStore((state) => state.liveMode);
  const selectedEventSequenceId = useInspectorStore(
    (state) => state.selectedEventSequenceId,
  );
  const setSelectedEventSequenceId = useInspectorStore(
    (state) => state.setSelectedEventSequenceId,
  );
  const selectedLogicalRequestId = useInspectorStore(
    (state) => state.selectedLogicalRequestId,
  );
  const setSelectedLogicalRequestId = useInspectorStore(
    (state) => state.setSelectedLogicalRequestId,
  );

  const deferredSearch = useDeferredValue(traceSearch);
  const [viewMode, setViewMode] = useState<TraceViewMode>("story");
  const [activeTraceKind, setActiveTraceKind] = useState<string>("");
  const [phaseFilter, setPhaseFilter] = useState("");
  const [statusCodeFilter, setStatusCodeFilter] = useState("");
  const [statusFamilyFilter, setStatusFamilyFilter] = useState("");
  const [llmPurposeFilter, setLlmPurposeFilter] = useState("");
  const [cacheHitFilter, setCacheHitFilter] = useState<TriState>("all");
  const [requestFailedFilter, setRequestFailedFilter] = useState<TriState>("all");
  const [transportErrorFilter, setTransportErrorFilter] = useState<TriState>("all");
  const [durationRange, setDurationRange] = useState<[number, number]>([0, 30_000]);
  const [timelineEvents, setTimelineEvents] = useState<UnifiedTraceEvent[]>([]);
  const [timelineCursor, setTimelineCursor] = useState(0);
  const [timelineRequestCursor, setTimelineRequestCursor] = useState<number | undefined>(
    undefined,
  );
  const [loadedChains, setLoadedChains] = useState<TraceChainSummary[]>([]);
  const [chainCursor, setChainCursor] = useState(0);
  const [chainRequestCursor, setChainRequestCursor] = useState<number | undefined>(
    undefined,
  );

  const filterOptions = useMemo(
    () => ({
      phase: phaseFilter || undefined,
      operationId: selectedOperationId ?? undefined,
      traceKind: activeTraceKind || undefined,
      statusCode: statusCodeFilter ? Number(statusCodeFilter) : undefined,
      statusFamily: statusFamilyFilter || undefined,
      search: deferredSearch || undefined,
      cacheHit: triStateToBoolean(cacheHitFilter),
      requestFailed: triStateToBoolean(requestFailedFilter),
      transportError: triStateToBoolean(transportErrorFilter),
      llmPurpose: llmPurposeFilter || undefined,
      minDurationMs: durationRange[0],
      maxDurationMs: durationRange[1],
    }),
    [
      activeTraceKind,
      cacheHitFilter,
      deferredSearch,
      durationRange,
      llmPurposeFilter,
      phaseFilter,
      requestFailedFilter,
      selectedOperationId,
      statusCodeFilter,
      statusFamilyFilter,
      transportErrorFilter,
    ],
  );

  useEffect(() => {
    setTimelineEvents([]);
    setLoadedChains([]);
    setTimelineCursor(0);
    setChainCursor(0);
    setTimelineRequestCursor(undefined);
    setChainRequestCursor(undefined);
    setSelectedEventSequenceId(null);
    setSelectedLogicalRequestId(null);
  }, [
    datasetId,
    runId,
    filterOptions,
    setSelectedEventSequenceId,
    setSelectedLogicalRequestId,
  ]);

  const facetsQuery = useTraceFacets(datasetId, runId, filterOptions);

  const snapshotTimelineQuery = useTimeline(datasetId, runId, {
    ...filterOptions,
    afterEventSequenceId: timelineRequestCursor,
    limit: 400,
    includePayload: false,
  });

  useEffect(() => {
    if (!snapshotTimelineQuery.data) {
      return;
    }
    setTimelineEvents((current) =>
      timelineRequestCursor == null
        ? snapshotTimelineQuery.data.events
        : mergeTimelineEvents(current, snapshotTimelineQuery.data.events),
    );
    setTimelineCursor(snapshotTimelineQuery.data.cursor);
  }, [snapshotTimelineQuery.data, timelineRequestCursor]);

  const shouldPoll = liveMode && runStatus === "running";
  const liveTimelineQuery = useTimeline(datasetId, runId, {
    ...filterOptions,
    enabled: shouldPoll,
    afterEventSequenceId: timelineCursor > 0 ? timelineCursor : undefined,
    includePayload: false,
    limit: 400,
    refetchInterval: shouldPoll ? 1500 : false,
  });

  useEffect(() => {
    if (!liveTimelineQuery.data || liveTimelineQuery.data.events.length === 0) {
      return;
    }
    setTimelineEvents((current) =>
      mergeTimelineEvents(current, liveTimelineQuery.data?.events ?? []),
    );
    setTimelineCursor(liveTimelineQuery.data.cursor);
  }, [liveTimelineQuery.data]);

  const needsChainQuery = viewMode === "story" || viewMode === "cards";
  const snapshotChainsQuery = useTraceChains(datasetId, runId, {
    ...filterOptions,
    enabled: needsChainQuery,
    afterEventSequenceId: chainRequestCursor,
    limit: 80,
  });

  useEffect(() => {
    if (!snapshotChainsQuery.data) {
      return;
    }
    setLoadedChains((current) =>
      chainRequestCursor == null
        ? snapshotChainsQuery.data.chains
        : mergeTraceChains(current, snapshotChainsQuery.data.chains),
    );
    setChainCursor(snapshotChainsQuery.data.cursor);
  }, [snapshotChainsQuery.data, chainRequestCursor]);

  const liveChainsQuery = useTraceChains(datasetId, runId, {
    ...filterOptions,
    enabled: needsChainQuery && shouldPoll,
    afterEventSequenceId: chainCursor > 0 ? chainCursor : undefined,
    limit: 80,
    refetchInterval: needsChainQuery && shouldPoll ? 1500 : false,
  });

  useEffect(() => {
    if (!liveChainsQuery.data || liveChainsQuery.data.chains.length === 0) {
      return;
    }
    setLoadedChains((current) =>
      mergeTraceChains(current, liveChainsQuery.data?.chains ?? []),
    );
    setChainCursor(liveChainsQuery.data.cursor);
  }, [liveChainsQuery.data]);

  const maxDuration = useMemo(
    () =>
      Math.max(
        1000,
        ...timelineEvents.map((event) => Math.round(event.durationMs ?? 0)),
      ),
    [timelineEvents],
  );

  useEffect(() => {
    setDurationRange((previous) => [
      Math.min(previous[0], maxDuration),
      Math.min(previous[1], maxDuration),
    ]);
  }, [maxDuration]);

  const selectedEventLight = useMemo(
    () => getEventBySequence(timelineEvents, selectedEventSequenceId),
    [timelineEvents, selectedEventSequenceId],
  );

  const selectedChainFromLoaded = useMemo(
    () =>
      selectedLogicalRequestId == null
        ? loadedChains.find((chain) =>
            selectedEventSequenceId == null
              ? false
              : chain.items.some(
                  (item) => item.eventSequenceId === selectedEventSequenceId,
                ),
          )
        : loadedChains.find((chain) => chain.logicalRequestId === selectedLogicalRequestId),
    [loadedChains, selectedEventSequenceId, selectedLogicalRequestId],
  );

  const effectiveLogicalRequestId =
    selectedLogicalRequestId ?? selectedEventLight?.logicalRequestId ?? null;

  const selectedChainQuery = useTimeline(datasetId, runId, {
    enabled: effectiveLogicalRequestId != null,
    logicalRequestId: effectiveLogicalRequestId ?? undefined,
    includePayload: true,
    limit: 500,
  });

  const selectedChain = useMemo<TraceChainSummary | undefined>(() => {
    if (selectedChainQuery.data?.events.length) {
      return buildTraceChains(selectedChainQuery.data.events)[0];
    }
    return selectedChainFromLoaded;
  }, [selectedChainFromLoaded, selectedChainQuery.data?.events]);

  const selectedFullEvent = useMemo(
    () =>
      selectedChainQuery.data?.events.find(
        (event) => event.eventSequenceId === selectedEventSequenceId,
      ) ?? selectedEventLight,
    [selectedChainQuery.data?.events, selectedEventLight, selectedEventSequenceId],
  );

  const handleSelectEvent = (
    eventSequenceId: number,
    logicalRequestId: number | null,
  ) => {
    setSelectedEventSequenceId(eventSequenceId);
    setSelectedLogicalRequestId(logicalRequestId);
  };

  const handleSelectChain = (chain: TraceChainSummary) => {
    setSelectedLogicalRequestId(chain.logicalRequestId ?? null);
    setSelectedEventSequenceId(chain.items[0]?.eventSequenceId ?? null);
  };

  const facetOptions = {
    operations: facetsQuery.data?.operations ?? [],
    phases: facetsQuery.data?.phases ?? [],
    statusCodes: facetsQuery.data?.statusCodes ?? [],
    statusFamilies: facetsQuery.data?.statusFamilies ?? [],
    traceKinds: facetsQuery.data?.traceKinds ?? [],
    llmPurposes: facetsQuery.data?.llmPurposes ?? [],
  };

  const eventCount = Number(facetsQuery.data?.totals.events ?? timelineEvents.length);
  const chainCount = loadedChains.length;
  const loadMoreAvailable =
    needsChainQuery
      ? (snapshotChainsQuery.data?.hasMore ?? false)
      : (snapshotTimelineQuery.data?.hasMore ?? false);

  return (
    <div className="space-y-4">
      <Panel title="Trace explorer">
        <TraceViewControls
          viewMode={viewMode}
          operationOptions={facetOptions.operations}
          operationFilter={selectedOperationId}
          phaseOptions={facetOptions.phases}
          phaseFilter={phaseFilter}
          search={traceSearch}
          traceKind={activeTraceKind}
          traceKindOptions={facetOptions.traceKinds}
          statusCodeFilter={statusCodeFilter}
          statusCodeOptions={facetOptions.statusCodes}
          statusFamilyFilter={statusFamilyFilter}
          statusFamilyOptions={facetOptions.statusFamilies}
          llmPurposeFilter={llmPurposeFilter}
          llmPurposeOptions={facetOptions.llmPurposes}
          cacheHitFilter={cacheHitFilter}
          requestFailedFilter={requestFailedFilter}
          transportErrorFilter={transportErrorFilter}
          durationRange={durationRange}
          maxDuration={maxDuration}
          eventCount={eventCount}
          chainCount={chainCount}
          onViewModeChange={setViewMode}
          onOperationFilterChange={setSelectedOperationId}
          onPhaseFilterChange={setPhaseFilter}
          onSearchChange={setTraceSearch}
          onTraceKindChange={setActiveTraceKind}
          onStatusCodeFilterChange={setStatusCodeFilter}
          onStatusFamilyFilterChange={setStatusFamilyFilter}
          onLlmPurposeFilterChange={setLlmPurposeFilter}
          onCacheHitFilterChange={(value) => setCacheHitFilter(value as TriState)}
          onRequestFailedFilterChange={(value) =>
            setRequestFailedFilter(value as TriState)
          }
          onTransportErrorFilterChange={(value) =>
            setTransportErrorFilter(value as TriState)
          }
          onDurationRangeChange={setDurationRange}
        />
      </Panel>

      {facetsQuery.data?.warnings.length ? (
        <Alert severity="warning" variant="outlined">
          {facetsQuery.data.warnings.join(" ")}
        </Alert>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Chip label={`Status codes: ${facetOptions.statusCodes.length}`} />
        <Chip label={`Phases: ${facetOptions.phases.length}`} variant="outlined" />
        <Chip
          label={`Cache hits: ${facetsQuery.data?.cacheHitCounts.true ?? 0}`}
          variant="outlined"
        />
        <Chip
          label={`Transport errors: ${facetsQuery.data?.transportErrorCounts.true ?? 0}`}
          variant="outlined"
        />
      </div>

      <TraceDensityStrip events={timelineEvents} onSelectEvent={handleSelectEvent} />

      <Stack
        direction={{ xs: "column", xl: "row" }}
        spacing={2}
        sx={{ alignItems: "flex-start" }}
      >
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2 px-1 text-xs uppercase tracking-wide text-slate">
            <span>{eventCount} filtered events</span>
            <span>{chainCount} loaded sequences</span>
            <Chip
              size="small"
              label={
                shouldPoll ? "Live incremental" : "Server-filtered snapshot"
              }
              color={shouldPoll ? "secondary" : "default"}
            />
          </div>

          <TraceViewSurface
            viewMode={viewMode}
            timelineEvents={timelineEvents}
            visibleChains={loadedChains}
            selectedEventSequenceId={selectedEventSequenceId}
            selectedLogicalRequestId={selectedLogicalRequestId}
            onSelectEvent={handleSelectEvent}
            onSelectChain={handleSelectChain}
          />

          {loadMoreAvailable ? (
            <div className="flex justify-center">
              <Button
                variant="outlined"
                onClick={() => {
                  if (needsChainQuery) {
                    setChainRequestCursor(chainCursor || undefined);
                  } else {
                    setTimelineRequestCursor(timelineCursor || undefined);
                  }
                }}
              >
                Load more
              </Button>
            </div>
          ) : null}
        </div>

        <div className="w-full xl:sticky xl:top-0 xl:w-[420px] xl:self-start">
          <TraceDetailDrawer
            sticky={false}
            selectedChain={selectedChain}
            selectedEvent={selectedFullEvent}
          />
        </div>
      </Stack>
    </div>
  );
}

type TraceViewSurfaceProps = {
  viewMode: TraceViewMode;
  timelineEvents: UnifiedTraceEvent[];
  visibleChains: TraceChainSummary[];
  selectedEventSequenceId: number | null;
  selectedLogicalRequestId: number | null;
  onSelectEvent: (eventSequenceId: number, logicalRequestId: number | null) => void;
  onSelectChain: (chain: TraceChainSummary) => void;
};

function TraceViewSurface({
  viewMode,
  timelineEvents,
  visibleChains,
  selectedEventSequenceId,
  selectedLogicalRequestId,
  onSelectEvent,
  onSelectChain,
}: TraceViewSurfaceProps) {
  const needsChains = viewMode === "story" || viewMode === "cards";
  if (!needsChains && timelineEvents.length === 0) {
    return (
      <Alert severity="info" variant="outlined">
        No trace events match the current filter combination.
      </Alert>
    );
  }
  if (needsChains && visibleChains.length === 0) {
    return (
      <Alert severity="info" variant="outlined">
        No trace sequences match the current filter combination.
      </Alert>
    );
  }

  if (viewMode === "story") {
    return (
      <TraceSequenceStory
        chains={visibleChains}
        selectedLogicalRequestId={selectedLogicalRequestId}
        selectedEventSequenceId={selectedEventSequenceId}
        onSelectChain={onSelectChain}
        onSelectEvent={onSelectEvent}
      />
    );
  }

  if (viewMode === "swimlanes") {
    return (
      <TracePhaseSwimlanes
        events={timelineEvents}
        selectedEventSequenceId={selectedEventSequenceId}
        onSelectEvent={onSelectEvent}
      />
    );
  }

  if (viewMode === "ribbon") {
    return (
      <TraceSequenceRibbon
        events={timelineEvents}
        selectedEventSequenceId={selectedEventSequenceId}
        onSelectEvent={onSelectEvent}
      />
    );
  }

  if (viewMode === "ledger") {
    return (
      <TraceLedger
        events={timelineEvents}
        selectedEventSequenceId={selectedEventSequenceId}
        onSelectEvent={onSelectEvent}
      />
    );
  }

  return (
    <TraceChainBoard
      chains={visibleChains}
      selectedEventSequenceId={selectedEventSequenceId}
      selectedLogicalRequestId={selectedLogicalRequestId}
      onSelectChain={onSelectChain}
      onSelectEvent={(chain, eventSequenceId, logicalRequestId) =>
        onSelectEvent(eventSequenceId, logicalRequestId ?? chain.logicalRequestId ?? null)
      }
    />
  );
}
