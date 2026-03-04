import {
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from "@mui/material";

import { TraceChainSummary } from "@/lib/schemas/api";
import { formatCompactNumber, formatDate } from "@/lib/formatters/format";

import { TraceEventChip } from "./trace-event-chip";

type TraceChainCardProps = {
  chain: TraceChainSummary;
  expanded: boolean;
  selectedEventSequenceId: number | null;
  onSelectChain: (chain: TraceChainSummary) => void;
  onSelectEvent: (
    chain: TraceChainSummary,
    eventSequenceId: number,
    logicalRequestId: number | null,
  ) => void;
};

const COLLAPSED_ITEMS = 8;

export function TraceChainCard({
  chain,
  expanded,
  selectedEventSequenceId,
  onSelectChain,
  onSelectEvent,
}: TraceChainCardProps) {
  const visibleItems = expanded ? chain.items : chain.items.slice(0, COLLAPSED_ITEMS);
  const hiddenCount = Math.max(0, chain.items.length - visibleItems.length);

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 4,
        backgroundColor: "background.paper",
        borderColor:
          expanded || chain.hasError ? "rgba(210, 139, 54, 0.38)" : "divider",
      }}
    >
      <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
        <button
          type="button"
          onClick={() => onSelectChain(chain)}
          className="w-full cursor-pointer rounded-2xl border-0 bg-transparent p-0 text-left"
        >
          <Stack spacing={1.5}>
            <Stack
              direction={{ xs: "column", md: "row" }}
              spacing={1.25}
              sx={{ justifyContent: "space-between", alignItems: { md: "center" } }}
            >
              <div>
                <Typography variant="subtitle1" fontWeight={700}>
                  {chain.operationId ?? chain.chainId}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {chain.phase ?? "unknown phase"} • {formatDate(chain.startedAt)}
                </Typography>
              </div>
              <Stack direction="row" flexWrap="wrap" gap={1}>
                <Chip size="small" label={`${chain.httpAttemptCount} HTTP`} />
                <Chip size="small" label={`${chain.llmCallCount} LLM`} />
                {chain.hasRetry ? (
                  <Chip size="small" color="warning" label="Retries" />
                ) : null}
                {chain.hasError ? (
                  <Chip size="small" color="error" label="Errors" />
                ) : null}
                {typeof chain.dominantStatusCode === "number" ? (
                  <Chip
                    size="small"
                    variant="outlined"
                    label={`Status ${chain.dominantStatusCode}`}
                  />
                ) : null}
              </Stack>
            </Stack>

            <Stack direction="row" spacing={1.25} useFlexGap flexWrap="wrap">
              <MetricBadge
                label="Duration"
                value={`${formatCompactNumber(chain.durationMs)} ms`}
              />
              <MetricBadge
                label="Range"
                value={`#${chain.eventSequenceStart} → #${chain.eventSequenceEnd}`}
              />
              <MetricBadge
                label="Items"
                value={String(chain.items.length)}
              />
            </Stack>
          </Stack>
        </button>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {visibleItems.map((item) => (
            <TraceEventChip
              key={item.eventSequenceId}
              item={item}
              selected={selectedEventSequenceId === item.eventSequenceId}
              onClick={() =>
                onSelectEvent(chain, item.eventSequenceId, item.logicalRequestId ?? null)
              }
            />
          ))}
          {hiddenCount > 0 ? (
            <Chip
              label={`+${hiddenCount} more`}
              onClick={() => onSelectChain(chain)}
              clickable
              variant="outlined"
            />
          ) : null}
        </div>

        <div className="mt-3 text-xs text-slate">
          {visibleItems.map((item) => item.summaryLabel).join(" • ")}
        </div>
      </CardContent>
    </Card>
  );
}

function MetricBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-paper px-3 py-2 text-xs">
      <div className="uppercase tracking-wide text-slate">{label}</div>
      <div className="mt-1 font-medium text-ink">{value}</div>
    </div>
  );
}
