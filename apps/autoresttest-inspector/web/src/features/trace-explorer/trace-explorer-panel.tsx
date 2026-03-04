import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import {
  Autocomplete,
  Box,
  Chip,
  FormControlLabel,
  Slider,
  Stack,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import { Panel } from "@/components/common/panel";
import { useTimeline, useTraceChains } from "@/lib/api/hooks";
import { TraceChainSummary } from "@/lib/schemas/api";
import { useInspectorStore } from "@/lib/state/inspector-store";

import { TraceChainBoard } from "./trace-chain-board";
import { TraceDensityStrip } from "./trace-density-strip";
import { TraceDetailDrawer } from "./trace-detail-drawer";
import { mergeTimelineIntoChains } from "./trace-grouping";

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
  const [activeTraceKind, setActiveTraceKind] = useState<string>("");
  const [phaseFilters, setPhaseFilters] = useState<string[]>([]);
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [retriesOnly, setRetriesOnly] = useState(false);
  const [durationRange, setDurationRange] = useState<[number, number]>([0, 30_000]);
  const [chains, setChains] = useState<TraceChainSummary[]>([]);
  const [cursor, setCursor] = useState<number>(0);
  const parentRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSelectedEventSequenceId(null);
    setSelectedLogicalRequestId(null);
    setChains([]);
    setCursor(0);
  }, [
    datasetId,
    runId,
    deferredSearch,
    activeTraceKind,
    selectedOperationId,
    setSelectedEventSequenceId,
    setSelectedLogicalRequestId,
  ]);

  const traceChainsQuery = useTraceChains(datasetId, runId, {
    operationId: selectedOperationId ?? undefined,
    traceKind: activeTraceKind || undefined,
    search: deferredSearch || undefined,
    limit: 200,
  });

  useEffect(() => {
    if (!traceChainsQuery.data) {
      return;
    }
    setChains(traceChainsQuery.data.chains);
    setCursor(traceChainsQuery.data.cursor);
  }, [traceChainsQuery.data]);

  const shouldPoll = liveMode && runStatus === "running";
  const liveTimelineQuery = useTimeline(datasetId, runId, {
    enabled: shouldPoll,
    operationId: selectedOperationId ?? undefined,
    traceKind: activeTraceKind || undefined,
    search: deferredSearch || undefined,
    afterEventSequenceId: cursor > 0 ? cursor : undefined,
    includePayload: false,
    refetchInterval: shouldPoll ? 1500 : false,
  });

  useEffect(() => {
    if (!liveTimelineQuery.data || liveTimelineQuery.data.events.length === 0) {
      return;
    }
    setChains((previous) =>
      mergeTimelineIntoChains(previous, liveTimelineQuery.data?.events ?? []),
    );
    setCursor(liveTimelineQuery.data.cursor);
  }, [liveTimelineQuery.data]);

  const maxDuration = useMemo(
    () =>
      Math.max(
        1000,
        ...chains.map((chain) => Math.round(chain.durationMs ?? 0)),
      ),
    [chains],
  );

  useEffect(() => {
    setDurationRange((previous) => [
      Math.min(previous[0], maxDuration),
      Math.min(Math.max(previous[1], maxDuration), maxDuration),
    ]);
  }, [maxDuration]);

  const phases = useMemo(
    () =>
      Array.from(
        new Set(
          chains
            .map((chain) => chain.phase)
            .filter((phase): phase is string => Boolean(phase)),
        ),
      ).sort(),
    [chains],
  );

  const operationOptions = useMemo(
    () =>
      Array.from(
        new Set(
          chains
            .map((chain) => chain.operationId)
            .filter((operationId): operationId is string => Boolean(operationId)),
        ),
      ).sort(),
    [chains],
  );

  const visibleChains = useMemo(() => {
    return chains.filter((chain) => {
      if (phaseFilters.length > 0 && (!chain.phase || !phaseFilters.includes(chain.phase))) {
        return false;
      }
      const duration = chain.durationMs ?? 0;
      if (duration < durationRange[0] || duration > durationRange[1]) {
        return false;
      }
      if (errorsOnly && !chain.hasError) {
        return false;
      }
      if (retriesOnly && !chain.hasRetry) {
        return false;
      }
      return true;
    });
  }, [chains, phaseFilters, durationRange, errorsOnly, retriesOnly]);

  const selectedChain = useMemo(() => {
    if (selectedLogicalRequestId != null) {
      return visibleChains.find(
        (chain) => chain.logicalRequestId === selectedLogicalRequestId,
      );
    }
    if (selectedEventSequenceId != null) {
      return visibleChains.find((chain) =>
        chain.items.some((item) => item.eventSequenceId === selectedEventSequenceId),
      );
    }
    return undefined;
  }, [selectedLogicalRequestId, selectedEventSequenceId, visibleChains]);

  const selectedChainTimelineQuery = useTimeline(datasetId, runId, {
    enabled: selectedLogicalRequestId != null,
    logicalRequestId: selectedLogicalRequestId ?? undefined,
    includePayload: true,
    limit: 200,
  });

  const selectedFullEvent = useMemo(() => {
    const events = selectedChainTimelineQuery.data?.events ?? [];
    if (selectedEventSequenceId != null) {
      return events.find(
        (event) => event.eventSequenceId === selectedEventSequenceId,
      );
    }
    return events[0];
  }, [selectedChainTimelineQuery.data?.events, selectedEventSequenceId]);

  return (
    <div className="space-y-4">
      <Panel title="Trace chains">
        <Stack spacing={2}>
          <Stack
            direction={{ xs: "column", xl: "row" }}
            spacing={1.5}
            useFlexGap
            sx={{ alignItems: { xl: "center" }, justifyContent: "space-between" }}
          >
            <Stack direction={{ xs: "column", lg: "row" }} spacing={1.5} useFlexGap>
              <Autocomplete
                size="small"
                sx={{ minWidth: 300 }}
                options={operationOptions}
                value={selectedOperationId}
                onChange={(_, value) => setSelectedOperationId(value)}
                renderInput={(params) => (
                  <TextField {...params} label="Operation filter" />
                )}
              />
              <TextField
                size="small"
                label="Search"
                placeholder="Search raw payload..."
                value={traceSearch}
                onChange={(event) => setTraceSearch(event.target.value)}
              />
            </Stack>

            <ToggleButtonGroup
              exclusive
              size="small"
              value={activeTraceKind}
              onChange={(_, value: string | null) => setActiveTraceKind(value ?? "")}
            >
              <ToggleButton value="">All traces</ToggleButton>
              <ToggleButton value="logical_request">Logical</ToggleButton>
              <ToggleButton value="http_attempt">HTTP</ToggleButton>
              <ToggleButton value="llm_call">LLM</ToggleButton>
            </ToggleButtonGroup>
          </Stack>

          <Stack
            direction={{ xs: "column", xl: "row" }}
            spacing={2}
            useFlexGap
            sx={{ alignItems: { xl: "center" }, justifyContent: "space-between" }}
          >
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              {phases.map((phase) => {
                const active = phaseFilters.includes(phase);
                return (
                  <Chip
                    key={phase}
                    label={phase}
                    color={active ? "secondary" : "default"}
                    variant={active ? "filled" : "outlined"}
                    onClick={() =>
                      setPhaseFilters((previous) =>
                        previous.includes(phase)
                          ? previous.filter((item) => item !== phase)
                          : [...previous, phase],
                      )
                    }
                  />
                );
              })}
            </Box>

            <Stack direction={{ xs: "column", md: "row" }} spacing={2} useFlexGap>
              <FormControlLabel
                control={
                  <Switch
                    checked={errorsOnly}
                    onChange={(event) => setErrorsOnly(event.target.checked)}
                  />
                }
                label="Errors only"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={retriesOnly}
                    onChange={(event) => setRetriesOnly(event.target.checked)}
                  />
                }
                label="Retries only"
              />
            </Stack>
          </Stack>

          <Box sx={{ px: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Duration filter ({Math.round(durationRange[0])} ms to {Math.round(durationRange[1])} ms)
            </Typography>
            <Slider
              value={durationRange}
              min={0}
              max={maxDuration}
              onChange={(_, value) =>
                setDurationRange(value as [number, number])
              }
              valueLabelDisplay="auto"
            />
          </Box>
        </Stack>
      </Panel>

      <TraceDensityStrip
        chains={visibleChains}
        onSelectEvent={(eventSequenceId, logicalRequestId) => {
          setSelectedEventSequenceId(eventSequenceId);
          setSelectedLogicalRequestId(logicalRequestId);
        }}
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_420px]">
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1 text-xs uppercase tracking-wide text-slate">
            <span>{visibleChains.length} chains visible</span>
            <span>
              {liveTimelineQuery.data?.timelineOrder ??
                traceChainsQuery.data?.warnings?.[0] ??
                "snapshot"}
            </span>
          </div>
          <TraceChainBoard
            parentRef={parentRef}
            chains={visibleChains}
            selectedEventSequenceId={selectedEventSequenceId}
            selectedLogicalRequestId={selectedLogicalRequestId}
            onSelectChain={(chain) => {
              setSelectedLogicalRequestId(chain.logicalRequestId ?? null);
              setSelectedEventSequenceId(chain.items[0]?.eventSequenceId ?? null);
            }}
            onSelectEvent={(chain, eventSequenceId, logicalRequestId) => {
              setSelectedLogicalRequestId(
                logicalRequestId ?? chain.logicalRequestId ?? null,
              );
              setSelectedEventSequenceId(eventSequenceId);
            }}
          />
        </div>

        <TraceDetailDrawer
          selectedChain={selectedChain}
          selectedEvent={selectedFullEvent}
        />
      </div>
    </div>
  );
}
