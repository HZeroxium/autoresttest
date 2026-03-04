import { RefObject } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

import { TraceChainSummary } from "@/lib/schemas/api";

import { TraceChainCard } from "./trace-chain-card";

type TraceChainBoardProps = {
  parentRef: RefObject<HTMLDivElement | null>;
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
  parentRef,
  chains,
  selectedEventSequenceId,
  selectedLogicalRequestId,
  onSelectChain,
  onSelectEvent,
}: TraceChainBoardProps) {
  const rowVirtualizer = useVirtualizer({
    count: chains.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 228,
    overscan: 6,
  });

  return (
    <div ref={parentRef} className="h-[720px] overflow-auto rounded-3xl bg-paper">
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          position: "relative",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const chain = chains[virtualRow.index];
          return (
            <div
              key={chain.chainId}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
                padding: "12px",
              }}
            >
              <TraceChainCard
                chain={chain}
                expanded={selectedLogicalRequestId === chain.logicalRequestId}
                selectedEventSequenceId={selectedEventSequenceId}
                onSelectChain={onSelectChain}
                onSelectEvent={onSelectEvent}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
