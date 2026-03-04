import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Chip,
  Paper,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";

import { TraceChainSummary, UnifiedTraceEvent } from "@/lib/schemas/api";
import { formatDate } from "@/lib/formatters/format";

type TraceDetailDrawerProps = {
  selectedChain?: TraceChainSummary;
  selectedEvent?: UnifiedTraceEvent;
  sticky?: boolean;
};

function SafePre({
  value,
  maxHeight = 380,
}: {
  value: unknown;
  maxHeight?: number;
}) {
  return (
    <pre
      className="overflow-auto rounded-2xl bg-paper p-4 text-xs text-ink"
      style={{ maxHeight }}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export function TraceDetailDrawer({
  selectedChain,
  selectedEvent,
  sticky = true,
}: TraceDetailDrawerProps) {
  const [tab, setTab] = useState(0);

  const httpHeaders = useMemo(() => {
    if (!selectedEvent || selectedEvent.traceKind !== "http_attempt") {
      return null;
    }
    const response = selectedEvent.payload.response;
    if (
      typeof response === "object" &&
      response !== null &&
      "headers" in response &&
      typeof (response as { headers?: unknown }).headers === "object"
    ) {
      return (response as { headers: unknown }).headers;
    }
    return null;
  }, [selectedEvent]);

  const tabs = ["Summary", "Payload", ...(httpHeaders ? ["Headers"] : []), "Raw JSON"];
  const safeTab = Math.min(tab, tabs.length - 1);

  useEffect(() => {
    if (safeTab !== tab) {
      setTab(safeTab);
    }
  }, [safeTab, tab]);

  if (!selectedEvent) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 2.5,
          minHeight: 320,
          borderRadius: 4,
          position: sticky ? "sticky" : "relative",
          top: sticky ? 0 : "auto",
        }}
      >
        <Typography variant="h6">Event detail</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Click an event block in a trace chain to inspect the exact request,
          response, or LLM interaction.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2.5,
        minHeight: 320,
        borderRadius: 4,
        position: sticky ? "sticky" : "relative",
        top: sticky ? 0 : "auto",
      }}
    >
      <Stack spacing={2}>
        <div>
          <Typography variant="overline" color="text.secondary">
            Selected event
          </Typography>
          <Typography variant="h6">
            {selectedEvent.summaryLabel ?? selectedEvent.kindLabel ?? selectedEvent.traceKind}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {selectedEvent.operationId ?? "No operation"} • {formatDate(selectedEvent.timestamp)}
          </Typography>
        </div>

        <Stack direction="row" flexWrap="wrap" gap={1}>
          <Chip label={`#${selectedEvent.eventSequenceId}`} />
          <Chip label={selectedEvent.traceKind.replace("_", " ")} variant="outlined" />
          {selectedEvent.statusCode ? (
            <Chip label={`Status ${selectedEvent.statusCode}`} variant="outlined" />
          ) : null}
          {selectedEvent.isRetry ? <Chip label="Retry" color="warning" /> : null}
          {selectedEvent.isError ? <Chip label="Error" color="error" /> : null}
          {selectedChain?.logicalRequestId != null ? (
            <Chip
              label={`Logical #${selectedChain.logicalRequestId}`}
              variant="outlined"
            />
          ) : null}
        </Stack>

        <Tabs value={safeTab} onChange={(_, value) => setTab(value)}>
          {tabs.map((tabLabel) => (
            <Tab key={tabLabel} label={tabLabel} />
          ))}
        </Tabs>

        <Box>
          {tabs[safeTab] === "Summary" ? (
            <Stack spacing={1.5}>
              <SummaryRow label="Phase" value={selectedEvent.phase ?? "n/a"} />
              <SummaryRow label="Component" value={selectedEvent.component ?? "n/a"} />
              <SummaryRow
                label="Duration"
                value={
                  typeof selectedEvent.durationMs === "number"
                    ? `${selectedEvent.durationMs.toFixed(2)} ms`
                    : "n/a"
                }
              />
              <SummaryRow
                label="Logical request"
                value={
                  selectedEvent.logicalRequestId != null
                    ? String(selectedEvent.logicalRequestId)
                    : "n/a"
                }
              />
              {selectedEvent.traceKind === "http_attempt" ? (
                <>
                  <SummaryRow
                    label="Method"
                    value={String(selectedEvent.payload.http_method ?? "n/a")}
                  />
                  <SummaryRow
                    label="URL"
                    value={String(selectedEvent.payload.url ?? "n/a")}
                    mono
                  />
                </>
              ) : null}
              {selectedEvent.traceKind === "llm_call" ? (
                <SummaryRow
                  label="LLM purpose"
                  value={selectedEvent.llmPurpose ?? "n/a"}
                />
              ) : null}
            </Stack>
          ) : null}

          {tabs[safeTab] === "Payload" ? (
            <Stack spacing={1.5}>
              {selectedEvent.traceKind === "http_attempt" ? (
                <>
                  <Typography variant="subtitle2">Request</Typography>
                  <SafePre
                    value={{
                      method: selectedEvent.payload.http_method,
                      url: selectedEvent.payload.url,
                      query_params: selectedEvent.payload.query_params,
                      request_headers: selectedEvent.payload.request_headers,
                      request_body: selectedEvent.payload.request_body,
                    }}
                  />
                  <Typography variant="subtitle2">Response</Typography>
                  <SafePre value={selectedEvent.payload.response} />
                </>
              ) : null}
              {selectedEvent.traceKind === "llm_call" ? (
                <>
                  <Typography variant="subtitle2">Prompt / response</Typography>
                  <SafePre
                    value={{
                      prompt: selectedEvent.payload.prompt,
                      system_prompt: selectedEvent.payload.system_prompt,
                      response: selectedEvent.payload.response,
                    }}
                  />
                </>
              ) : null}
              {selectedEvent.traceKind === "logical_request" ? (
                <SafePre value={selectedEvent.payload} />
              ) : null}
            </Stack>
          ) : null}

          {tabs[safeTab] === "Headers" ? <SafePre value={httpHeaders} /> : null}

          {tabs[safeTab] === "Raw JSON" ? <SafePre value={selectedEvent.payload} /> : null}
        </Box>
      </Stack>
    </Paper>
  );
}

function SummaryRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-2xl bg-paper p-3">
      <div className="text-xs uppercase tracking-wide text-slate">{label}</div>
      <div className={`mt-1 text-sm text-ink ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}
