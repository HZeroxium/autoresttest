import {
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import { UnifiedTraceEvent } from "@/lib/schemas/api";
import { formatCompactNumber, formatDate, truncate } from "@/lib/formatters/format";

type TraceLedgerProps = {
  events: UnifiedTraceEvent[];
  selectedEventSequenceId: number | null;
  onSelectEvent: (eventSequenceId: number, logicalRequestId: number | null) => void;
};

export function TraceLedger({
  events,
  selectedEventSequenceId,
  onSelectEvent,
}: TraceLedgerProps) {
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
    <TableContainer
      component={Paper}
      variant="outlined"
      sx={{ borderRadius: 4, maxHeight: { xs: 520, xl: 760 } }}
    >
      <Table stickyHeader size="small">
        <TableHead>
          <TableRow>
            <TableCell>Seq</TableCell>
            <TableCell>Kind</TableCell>
            <TableCell>Phase</TableCell>
            <TableCell>Operation</TableCell>
            <TableCell>Summary</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Duration</TableCell>
            <TableCell>Timestamp</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {events.map((event) => {
            const selected = selectedEventSequenceId === event.eventSequenceId;
            return (
              <TableRow
                key={event.eventSequenceId}
                hover
                selected={selected}
                onClick={() =>
                  onSelectEvent(
                    event.eventSequenceId,
                    event.logicalRequestId ?? null,
                  )
                }
                sx={{ cursor: "pointer" }}
              >
                <TableCell sx={{ fontFamily: "IBM Plex Mono, monospace" }}>
                  #{event.eventSequenceId}
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={event.traceKind.replace("_", " ")}
                    color={
                      event.traceKind === "logical_request"
                        ? "primary"
                        : event.traceKind === "llm_call"
                          ? "info"
                          : event.isError
                            ? "error"
                            : "warning"
                    }
                    variant={event.traceKind === "http_attempt" ? "filled" : "outlined"}
                  />
                </TableCell>
                <TableCell>{event.phase ?? "n/a"}</TableCell>
                <TableCell>{event.operationId ?? "n/a"}</TableCell>
                <TableCell>
                  {truncate(
                    event.summaryLabel ?? event.kindLabel ?? event.traceKind,
                    72,
                  )}
                </TableCell>
                <TableCell>
                  {typeof event.statusCode === "number"
                    ? event.statusCode
                    : event.isError
                      ? "error"
                      : "n/a"}
                </TableCell>
                <TableCell>
                  {typeof event.durationMs === "number"
                    ? `${formatCompactNumber(event.durationMs)} ms`
                    : "n/a"}
                </TableCell>
                <TableCell>{formatDate(event.timestamp)}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
