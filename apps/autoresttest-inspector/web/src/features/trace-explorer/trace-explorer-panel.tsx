import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Alert, Chip, Stack } from "@mui/material";

import { Panel } from "@/components/common/panel";
import { useTimeline } from "@/lib/api/hooks";
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
  filterTimelineEvents,
  getEventBySequence,
  mergeTimelineEvents,
} from "./trace-grouping";
import { TraceViewControls } from "./trace-view-controls";

type TraceExplorerPanelProps = {
  datasetId: string;
  runId: string;
  runStatus: string;
};

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
  const [phaseFilters, setPhaseFilters] = useState<string[]>([]);
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [retriesOnly, setRetriesOnly] = useState(false);
  const [durationRange, setDurationRange] = useState<[number, number]>([0, 30_000]);
  const [timelineEvents, setTimelineEvents] = useState<UnifiedTraceEvent[]>([]);
  const [cursor, setCursor] = useState<number>(0);

  useEffect(() => {
    setTimelineEvents([]);
    setCursor(0);
    setSelectedEventSequenceId(null);
    setSelectedLogicalRequestId(null);
  }, [datasetId, runId, setSelectedEventSequenceId, setSelectedLogicalRequestId]);

  const snapshotTimelineQuery = useTimeline(datasetId, runId, {
    limit: 5000,
    includePayload: false,
  });

  useEffect(() => {
    if (!snapshotTimelineQuery.data) {
      return;
    }
    setTimelineEvents((current) =>
      current.length === 0
        ? snapshotTimelineQuery.data.events
        : mergeTimelineEvents(snapshotTimelineQuery.data.events, current),
    );
    setCursor(snapshotTimelineQuery.data.cursor);
  }, [snapshotTimelineQuery.data]);

  const shouldPoll = liveMode && runStatus === "running";
  const liveTimelineQuery = useTimeline(datasetId, runId, {
    enabled: shouldPoll,
    afterEventSequenceId: cursor > 0 ? cursor : undefined,
    includePayload: false,
    limit: 5000,
    refetchInterval: shouldPoll ? 1500 : false,
  });

  useEffect(() => {
    if (!liveTimelineQuery.data || liveTimelineQuery.data.events.length === 0) {
      return;
    }
    setTimelineEvents((current) =>
      mergeTimelineEvents(current, liveTimelineQuery.data?.events ?? []),
    );
    setCursor(liveTimelineQuery.data.cursor);
  }, [liveTimelineQuery.data]);

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

  const phases = useMemo(
    () =>
      Array.from(
        new Set(
          timelineEvents
            .map((event) => event.phase)
            .filter((phase): phase is string => Boolean(phase)),
        ),
      ).sort(),
    [timelineEvents],
  );

  const operationOptions = useMemo(
    () =>
      Array.from(
        new Set(
          timelineEvents
            .map((event) => event.operationId)
            .filter((operationId): operationId is string => Boolean(operationId)),
        ),
      ).sort(),
    [timelineEvents],
  );

  const filteredEvents = useMemo(
    () =>
      filterTimelineEvents(timelineEvents, {
        search: deferredSearch,
        operationId: selectedOperationId,
        traceKind: activeTraceKind,
        phases: phaseFilters,
        errorsOnly,
        retriesOnly,
        durationRange,
      }),
    [
      timelineEvents,
      deferredSearch,
      selectedOperationId,
      activeTraceKind,
      phaseFilters,
      errorsOnly,
      retriesOnly,
      durationRange,
    ],
  );

  const visibleChains = useMemo(
    () => buildTraceChains(filteredEvents),
    [filteredEvents],
  );

  const selectedEventLight = useMemo(
    () =>
      getEventBySequence(filteredEvents, selectedEventSequenceId) ??
      getEventBySequence(timelineEvents, selectedEventSequenceId),
    [filteredEvents, timelineEvents, selectedEventSequenceId],
  );

  const effectiveLogicalRequestId =
    selectedLogicalRequestId ?? selectedEventLight?.logicalRequestId ?? null;

  const selectedChainQuery = useTimeline(datasetId, runId, {
    enabled: effectiveLogicalRequestId != null,
    logicalRequestId: effectiveLogicalRequestId ?? undefined,
    includePayload: true,
    limit: 500,
  });

  const selectedOrphanEventQuery = useTimeline(datasetId, runId, {
    enabled:
      selectedEventSequenceId != null &&
      selectedEventLight?.logicalRequestId == null &&
      Boolean(selectedEventLight),
    includePayload: true,
    limit: 5000,
  });

  const selectedChain = useMemo<TraceChainSummary | undefined>(() => {
    if (selectedChainQuery.data?.events.length) {
      return buildTraceChains(selectedChainQuery.data.events)[0];
    }
    if (effectiveLogicalRequestId == null) {
      return visibleChains.find((chain) =>
        selectedEventSequenceId == null
          ? false
          : chain.items.some(
              (item) => item.eventSequenceId === selectedEventSequenceId,
            ),
      );
    }
    return visibleChains.find(
      (chain) => chain.logicalRequestId === effectiveLogicalRequestId,
    );
  }, [
    selectedChainQuery.data?.events,
    effectiveLogicalRequestId,
    visibleChains,
    selectedEventSequenceId,
  ]);

  const selectedFullEvent = useMemo(() => {
    if (selectedChainQuery.data?.events.length && selectedEventSequenceId != null) {
      return selectedChainQuery.data.events.find(
        (event) => event.eventSequenceId === selectedEventSequenceId,
      );
    }
    if (
      selectedOrphanEventQuery.data?.events.length &&
      selectedEventSequenceId != null
    ) {
      return selectedOrphanEventQuery.data.events.find(
        (event) => event.eventSequenceId === selectedEventSequenceId,
      );
    }
    return selectedEventLight;
  }, [
    selectedChainQuery.data?.events,
    selectedOrphanEventQuery.data?.events,
    selectedEventSequenceId,
    selectedEventLight,
  ]);

  const timelineOrder =
    liveTimelineQuery.data?.timelineOrder ?? snapshotTimelineQuery.data?.timelineOrder;
  const warnings =
    snapshotTimelineQuery.data?.warnings ?? liveTimelineQuery.data?.warnings ?? [];

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

  return (
    <div className="space-y-4">
      <Panel title="Trace explorer">
        <TraceViewControls
          viewMode={viewMode}
          operationOptions={operationOptions}
          operationFilter={selectedOperationId}
          search={traceSearch}
          traceKind={activeTraceKind}
          phaseFilters={phaseFilters}
          phases={phases}
          errorsOnly={errorsOnly}
          retriesOnly={retriesOnly}
          durationRange={durationRange}
          maxDuration={maxDuration}
          eventCount={filteredEvents.length}
          chainCount={visibleChains.length}
          onViewModeChange={setViewMode}
          onOperationFilterChange={setSelectedOperationId}
          onSearchChange={setTraceSearch}
          onTraceKindChange={setActiveTraceKind}
          onTogglePhase={(phase) =>
            setPhaseFilters((current) =>
              current.includes(phase)
                ? current.filter((item) => item !== phase)
                : [...current, phase],
            )
          }
          onErrorsOnlyChange={setErrorsOnly}
          onRetriesOnlyChange={setRetriesOnly}
          onDurationRangeChange={setDurationRange}
        />
      </Panel>

      {warnings.length > 0 ? (
        <Alert severity="warning" variant="outlined">
          {warnings.join(" ")}
        </Alert>
      ) : null}

      <TraceDensityStrip events={filteredEvents} onSelectEvent={handleSelectEvent} />

      <Stack
        direction={{ xs: "column", xl: "row" }}
        spacing={2}
        sx={{ alignItems: "flex-start" }}
      >
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2 px-1 text-xs uppercase tracking-wide text-slate">
            <span>{filteredEvents.length} events visible</span>
            <span>{visibleChains.length} sequences</span>
            {timelineOrder ? (
              <Chip size="small" label={`${timelineOrder} ordering`} />
            ) : null}
            <Chip
              size="small"
              color={runStatus === "running" && liveMode ? "secondary" : "default"}
              label={
                runStatus === "running" && liveMode
                  ? "Live incremental"
                  : "Static snapshot"
              }
            />
          </div>

          <TraceViewSurface
            viewMode={viewMode}
            filteredEvents={filteredEvents}
            visibleChains={visibleChains}
            selectedEventSequenceId={selectedEventSequenceId}
            selectedLogicalRequestId={selectedLogicalRequestId}
            onSelectEvent={handleSelectEvent}
            onSelectChain={handleSelectChain}
          />
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
  filteredEvents: UnifiedTraceEvent[];
  visibleChains: TraceChainSummary[];
  selectedEventSequenceId: number | null;
  selectedLogicalRequestId: number | null;
  onSelectEvent: (eventSequenceId: number, logicalRequestId: number | null) => void;
  onSelectChain: (chain: TraceChainSummary) => void;
};

function TraceViewSurface({
  viewMode,
  filteredEvents,
  visibleChains,
  selectedEventSequenceId,
  selectedLogicalRequestId,
  onSelectEvent,
  onSelectChain,
}: TraceViewSurfaceProps) {
  if (filteredEvents.length === 0) {
    return (
      <Alert severity="info" variant="outlined">
        No trace events match the current filter combination. Loosen the filters or
        switch to a different trace kind.
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
        events={filteredEvents}
        selectedEventSequenceId={selectedEventSequenceId}
        onSelectEvent={onSelectEvent}
      />
    );
  }

  if (viewMode === "ribbon") {
    return (
      <TraceSequenceRibbon
        events={filteredEvents}
        selectedEventSequenceId={selectedEventSequenceId}
        onSelectEvent={onSelectEvent}
      />
    );
  }

  if (viewMode === "ledger") {
    return (
      <TraceLedger
        events={filteredEvents}
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
