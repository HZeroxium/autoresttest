import { Chip, Paper, Stack, Tooltip, Typography } from "@mui/material";

import { UnifiedTraceEvent } from "@/lib/schemas/api";
import { truncate } from "@/lib/formatters/format";

type TraceSequenceRibbonProps = {
  events: UnifiedTraceEvent[];
  selectedEventSequenceId: number | null;
  onSelectEvent: (eventSequenceId: number, logicalRequestId: number | null) => void;
};

function colorForEvent(event: UnifiedTraceEvent) {
  if (event.traceKind === "logical_request") {
    return { background: "#12343b", foreground: "#f5f2e9" };
  }
  if (event.traceKind === "llm_call") {
    return event.cacheHit
      ? { background: "#3b7a57", foreground: "#eef7ef" }
      : { background: "#49677c", foreground: "#eef3f7" };
  }
  if (event.isError) {
    return { background: "#a54730", foreground: "#fff4f1" };
  }
  return { background: "#d28b36", foreground: "#fff7ea" };
}

export function TraceSequenceRibbon({
  events,
  selectedEventSequenceId,
  onSelectEvent,
}: TraceSequenceRibbonProps) {
  if (events.length === 0) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 4, p: 2.5 }}>
        <Typography variant="body2" color="text.secondary">
          No events match the current filters.
        </Typography>
      </Paper>
    );
  }

  return (
    <Stack spacing={2}>
      <Paper variant="outlined" sx={{ borderRadius: 4, p: 2 }}>
        <div className="overflow-x-auto pb-2">
          <div className="flex min-w-max items-center gap-2">
            {events.map((event, index) => {
              const colors = colorForEvent(event);
              const selected = selectedEventSequenceId === event.eventSequenceId;
              const nextLogicalId = events[index + 1]?.logicalRequestId ?? null;
              const currentLogicalId = event.logicalRequestId ?? null;
              const showDivider =
                index < events.length - 1 && currentLogicalId !== nextLogicalId;

              return (
                <div key={event.eventSequenceId} className="flex items-center gap-2">
                  <Tooltip
                    title={[
                      `#${event.eventSequenceId}`,
                      event.phase ?? "unknown phase",
                      event.summaryLabel ?? event.kindLabel ?? event.traceKind,
                    ].join(" | ")}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        onSelectEvent(
                          event.eventSequenceId,
                          event.logicalRequestId ?? null,
                        )
                      }
                      className="min-w-[104px] rounded-3xl border px-3 py-2 text-left transition-transform hover:-translate-y-0.5"
                      style={{
                        background: colors.background,
                        color: colors.foreground,
                        borderColor: selected ? "#12343b" : "rgba(18, 52, 59, 0.08)",
                        boxShadow: selected
                          ? "0 0 0 2px rgba(18, 52, 59, 0.24)"
                          : "none",
                      }}
                    >
                      <div className="text-[10px] font-semibold uppercase tracking-[0.14em]">
                        {event.traceKind.replace("_", " ")}
                      </div>
                      <div className="mt-1 font-mono text-xs">#{event.eventSequenceId}</div>
                      <div className="mt-1 text-[11px]">
                        {truncate(
                          event.summaryLabel ?? event.kindLabel ?? event.traceKind,
                          34,
                        )}
                      </div>
                    </button>
                  </Tooltip>
                  {showDivider ? (
                    <div className="h-10 w-0 rounded-full border-l border-dashed border-line" />
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </Paper>

      <div className="flex flex-wrap gap-1">
        <Chip label="Timeline filmstrip" />
        <Chip label="Dashed dividers = logical sequence boundary" variant="outlined" />
        <Chip label="Scroll horizontally for long runs" variant="outlined" />
      </div>
    </Stack>
  );
}
