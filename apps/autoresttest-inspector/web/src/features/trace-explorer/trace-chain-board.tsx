import { Stack } from "@mui/material";

import { TraceChainSummary } from "@/lib/schemas/api";

import { TraceChainCard } from "./trace-chain-card";

type TraceChainBoardProps = {
  chains: TraceChainSummary[];
  selectedEventSequenceId: number | null;
  selectedLogicalRequestId: number | null;
  onSelectChain: (chain: TraceChainSummary) => void;
  onSelectEvent: (
    chain: TraceChainSummary,
    eventSequenceId: number,
    logicalRequestId: number | null,
  ) => void;
};

export function TraceChainBoard({
  chains,
  selectedEventSequenceId,
  selectedLogicalRequestId,
  onSelectChain,
  onSelectEvent,
}: TraceChainBoardProps) {
  return (
    <div className="max-h-[min(76vh,980px)] overflow-auto rounded-3xl bg-paper p-1">
      <Stack spacing={1.5}>
        {chains.map((chain) => (
          <TraceChainCard
            key={chain.chainId}
            chain={chain}
            expanded={selectedLogicalRequestId === chain.logicalRequestId}
            selectedEventSequenceId={selectedEventSequenceId}
            onSelectChain={onSelectChain}
            onSelectEvent={onSelectEvent}
          />
        ))}
      </Stack>
    </div>
  );
}
