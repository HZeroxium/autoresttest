import { useMemo } from "react";
import { Alert, Box, Chip, Paper, Stack, Typography } from "@mui/material";
import ReactECharts from "echarts-for-react";

import { UnifiedTraceEvent } from "@/lib/schemas/api";
import { formatCompactNumber } from "@/lib/formatters/format";

type TracePhaseSwimlanesProps = {
  events: UnifiedTraceEvent[];
  selectedEventSequenceId: number | null;
  onSelectEvent: (eventSequenceId: number, logicalRequestId: number | null) => void;
};

function colorForEvent(event: UnifiedTraceEvent) {
  if (event.traceKind === "logical_request") {
    return "#12343b";
  }
  if (event.traceKind === "llm_call") {
    return event.cacheHit ? "#3b7a57" : "#49677c";
  }
  if (event.isError) {
    return "#a54730";
  }
  return "#d28b36";
}

export function TracePhaseSwimlanes({
  events,
  selectedEventSequenceId,
  onSelectEvent,
}: TracePhaseSwimlanesProps) {
  const phases = useMemo(() => {
    return Array.from(
      new Set(
        events
          .map((event) => event.phase ?? "unknown")
          .filter((phase): phase is string => Boolean(phase)),
      ),
    );
  }, [events]);

  const chartData = useMemo(() => {
    const phaseIndex = new Map(phases.map((phase, index) => [phase, index]));
    return events.map((event) => ({
      value: [
        event.eventSequenceId,
        phaseIndex.get(event.phase ?? "unknown") ?? 0,
        Math.max(8, Math.min(18, Math.round((event.durationMs ?? 0) / 250))),
      ],
      itemStyle: {
        color: colorForEvent(event),
        opacity:
          selectedEventSequenceId == null ||
          selectedEventSequenceId === event.eventSequenceId
            ? 0.92
            : 0.38,
      },
      eventSequenceId: event.eventSequenceId,
      logicalRequestId: event.logicalRequestId ?? null,
      traceKind: event.traceKind,
      summaryLabel: event.summaryLabel ?? event.kindLabel ?? event.traceKind,
      durationMs: event.durationMs ?? null,
      phase: event.phase ?? "unknown",
    }));
  }, [events, phases, selectedEventSequenceId]);

  if (events.length === 0) {
    return (
      <Alert severity="info" variant="outlined">
        No events match the current filters.
      </Alert>
    );
  }

  return (
    <Stack spacing={2}>
      <Paper variant="outlined" sx={{ borderRadius: 4, p: 1.5 }}>
        <ReactECharts
          style={{ height: Math.max(280, phases.length * 72) }}
          option={{
            animation: false,
            grid: { left: 160, right: 20, top: 20, bottom: 40 },
            xAxis: {
              type: "value",
              name: "Global event sequence",
              nameLocation: "middle",
              nameGap: 28,
              splitLine: { lineStyle: { color: "rgba(18, 52, 59, 0.06)" } },
            },
            yAxis: {
              type: "category",
              data: phases,
              axisLabel: {
                width: 140,
                overflow: "truncate",
              },
            },
            tooltip: {
              formatter: (params: {
                data: {
                  eventSequenceId: number;
                  traceKind: string;
                  summaryLabel: string;
                  durationMs: number | null;
                  phase: string;
                };
              }) =>
                [
                  `#${params.data.eventSequenceId}`,
                  params.data.phase,
                  params.data.traceKind.replace("_", " "),
                  params.data.summaryLabel,
                  `duration: ${
                    params.data.durationMs == null
                      ? "n/a"
                      : `${formatCompactNumber(params.data.durationMs)} ms`
                  }`,
                ].join("<br/>"),
            },
            series: [
              {
                type: "scatter",
                data: chartData,
                symbolSize: (value: number[]) => value[2],
              },
            ],
          }}
          onEvents={{
            click: (params: {
              data?: { eventSequenceId: number; logicalRequestId: number | null };
            }) => {
              if (params.data) {
                onSelectEvent(params.data.eventSequenceId, params.data.logicalRequestId);
              }
            },
          }}
        />
      </Paper>

      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
        <Chip label="Each lane = phase" />
        <Chip label="X-axis = global execution order" variant="outlined" />
        <Chip label="Point size = duration" variant="outlined" />
        <Chip label="Click a point to inspect the exact event" variant="outlined" />
      </Box>
    </Stack>
  );
}
