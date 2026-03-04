import { useMemo } from "react";
import { Paper } from "@mui/material";
import ReactECharts from "echarts-for-react";

import { TraceChainSummary } from "@/lib/schemas/api";

type TraceDensityStripProps = {
  chains: TraceChainSummary[];
  onSelectEvent: (eventSequenceId: number, logicalRequestId: number | null) => void;
};

function colorForTraceKind(traceKind: string, isError: boolean) {
  if (traceKind === "logical_request") {
    return "#12343b";
  }
  if (traceKind === "llm_call") {
    return "#49677c";
  }
  if (isError) {
    return "#a54730";
  }
  return "#d28b36";
}

export function TraceDensityStrip({
  chains,
  onSelectEvent,
}: TraceDensityStripProps) {
  const data = useMemo(
    () =>
      chains.flatMap((chain) =>
        chain.items.map((item) => ({
          value: [item.eventSequenceId, 1],
          itemStyle: { color: colorForTraceKind(item.traceKind, item.isError) },
          eventSequenceId: item.eventSequenceId,
          logicalRequestId: item.logicalRequestId,
        })),
      ),
    [chains],
  );

  return (
    <Paper variant="outlined" sx={{ borderRadius: 4, p: 1.25 }}>
      <ReactECharts
        style={{ height: 88 }}
        option={{
          animation: false,
          grid: { left: 24, right: 20, top: 8, bottom: 24 },
          xAxis: {
            type: "value",
            axisLabel: { fontSize: 10 },
            splitLine: { show: false },
          },
          yAxis: {
            type: "value",
            min: 0,
            max: 2,
            show: false,
          },
          tooltip: {
            formatter: (params: { data: { eventSequenceId: number; logicalRequestId: number | null } }) =>
              `#${params.data.eventSequenceId}${
                params.data.logicalRequestId != null
                  ? ` • logical ${params.data.logicalRequestId}`
                  : ""
              }`,
          },
          series: [
            {
              type: "scatter",
              symbolSize: 10,
              data,
            },
          ],
        }}
        onEvents={{
          click: (params: { data?: { eventSequenceId: number; logicalRequestId: number | null } }) => {
            if (params.data) {
              onSelectEvent(params.data.eventSequenceId, params.data.logicalRequestId);
            }
          },
        }}
      />
    </Paper>
  );
}
