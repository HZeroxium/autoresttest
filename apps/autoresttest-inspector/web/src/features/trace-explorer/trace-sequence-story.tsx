import { ButtonBase, Chip, Paper, Stack, Typography } from "@mui/material";

import { TraceChainSummary } from "@/lib/schemas/api";
import { formatCompactNumber, formatDate } from "@/lib/formatters/format";

import { groupChainsByPhase } from "./trace-grouping";

type TraceSequenceStoryProps = {
  chains: TraceChainSummary[];
  selectedLogicalRequestId: number | null;
  selectedEventSequenceId: number | null;
  onSelectChain: (chain: TraceChainSummary) => void;
  onSelectEvent: (eventSequenceId: number, logicalRequestId: number | null) => void;
};

const PREVIEW_COUNT = 5;

export function TraceSequenceStory({
  chains,
  selectedLogicalRequestId,
  selectedEventSequenceId,
  onSelectChain,
  onSelectEvent,
}: TraceSequenceStoryProps) {
  const sections = groupChainsByPhase(chains);

  return (
    <div className="space-y-5">
      {sections.map((section) => (
        <div key={section.phase} className="space-y-3">
          <div className="sticky top-0 z-[1] rounded-2xl border border-line bg-panel/95 px-4 py-2 backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <Typography variant="subtitle2">{section.phase}</Typography>
              <Chip size="small" label={`${section.chains.length} sequences`} />
            </div>
          </div>

          <div className="space-y-3">
            {section.chains.map((chain) => {
              const active = selectedLogicalRequestId === chain.logicalRequestId;
              const previewItems = active ? chain.items : chain.items.slice(0, PREVIEW_COUNT);
              const hiddenCount = Math.max(0, chain.items.length - previewItems.length);

              return (
                <Paper
                  key={chain.chainId}
                  variant="outlined"
                  sx={{
                    borderRadius: 4,
                    px: 2,
                    py: 1.75,
                    borderColor: active ? "secondary.main" : "divider",
                  }}
                >
                  <div className="grid gap-3 xl:grid-cols-[96px_minmax(0,1fr)]">
                    <div className="rounded-2xl bg-paper px-3 py-3 text-xs">
                      <div className="uppercase tracking-wide text-slate">Start</div>
                      <div className="mt-1 font-mono text-sm text-ink">
                        #{chain.eventSequenceStart}
                      </div>
                      <div className="mt-1 text-slate">
                        to #{chain.eventSequenceEnd}
                      </div>
                    </div>

                    <div className="space-y-3">
                      <ButtonBase
                        onClick={() => onSelectChain(chain)}
                        sx={{
                          display: "block",
                          width: "100%",
                          borderRadius: 3,
                          textAlign: "left",
                          px: 0.75,
                          py: 0.25,
                        }}
                      >
                        <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                          <div>
                            <Typography variant="subtitle1" fontWeight={700}>
                              {`Sequence #${chain.eventSequenceStart} -> #${chain.eventSequenceEnd}`}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {chain.operationId ?? chain.chainId} • {formatDate(chain.startedAt)} •{" "}
                              {formatCompactNumber(chain.durationMs)} ms
                            </Typography>
                          </div>
                          <div className="flex flex-wrap items-center gap-1">
                            <Chip size="small" label={`${chain.httpAttemptCount} HTTP`} />
                            <Chip size="small" label={`${chain.llmCallCount} LLM`} />
                            {chain.hasError ? (
                              <Chip size="small" color="error" label="Errors" />
                            ) : null}
                            {chain.hasRetry ? (
                              <Chip size="small" color="warning" label="Retries" />
                            ) : null}
                          </div>
                        </div>
                      </ButtonBase>

                      <div className="flex flex-wrap gap-2">
                        {previewItems.map((item) => {
                          const selected = selectedEventSequenceId === item.eventSequenceId;
                          return (
                            <button
                              key={item.eventSequenceId}
                              type="button"
                              onClick={() =>
                                onSelectEvent(item.eventSequenceId, item.logicalRequestId ?? null)
                              }
                              className={`rounded-2xl border px-3 py-2 text-left text-xs transition-colors ${
                                selected
                                  ? "border-accent bg-accent text-white"
                                  : "border-line bg-paper text-ink hover:border-accent"
                              }`}
                            >
                              <div className="font-semibold uppercase tracking-[0.12em]">
                                {item.traceKind.replace("_", " ")}
                              </div>
                              <div className="mt-1 font-mono">#{item.eventSequenceId}</div>
                              <div className="mt-1 text-[11px] opacity-80">
                                {item.summaryLabel}
                              </div>
                            </button>
                          );
                        })}
                        {hiddenCount > 0 ? (
                          <Chip
                            label={`+${hiddenCount} more`}
                            clickable
                            onClick={() => onSelectChain(chain)}
                            variant="outlined"
                          />
                        ) : null}
                      </div>
                    </div>
                  </div>
                </Paper>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
