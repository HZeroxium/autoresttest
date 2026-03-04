import { useMemo } from "react";
import { Paper } from "@mui/material";
import ReactECharts from "echarts-for-react";

import { GraphSnapshot } from "@/lib/schemas/api";

type GraphEdgeLayer = "effective" | "confirmed" | "tentative";

type DependencyMatrixProps = {
  graph?: GraphSnapshot;
  edgeLayers: GraphEdgeLayer[];
  selectedOperationId: string | null;
  onSelectOperation: (operationId: string | null) => void;
};

export function DependencyMatrix({
  graph,
  edgeLayers,
  selectedOperationId,
  onSelectOperation,
}: DependencyMatrixProps) {
  const { nodes, matrixData, maxValue } = useMemo(() => {
    if (!graph) {
      return { nodes: [], matrixData: [], maxValue: 1 };
    }

    const nodes = [...graph.nodes].sort((left, right) =>
      `${left.resourceGroup}:${left.id}`.localeCompare(
        `${right.resourceGroup}:${right.id}`,
      ),
    );
    const nodeIndex = new Map(nodes.map((node, index) => [node.id, index]));
    const matrixData: Array<[number, number, number, string, string, string, number]> =
      [];
    let maxValue = 1;
    for (const edge of graph.edges) {
      if (!edgeLayers.includes(edge.layer as GraphEdgeLayer)) {
        continue;
      }
      const sourceIndex = nodeIndex.get(edge.sourceId);
      const targetIndex = nodeIndex.get(edge.targetId);
      if (sourceIndex === undefined || targetIndex === undefined) {
        continue;
      }
      const weight =
        edge.maxSimilarity + (edge.layer === "effective" ? 0.25 : edge.layer === "confirmed" ? 0.12 : 0);
      maxValue = Math.max(maxValue, weight);
      matrixData.push([
        sourceIndex,
        targetIndex,
        Number(weight.toFixed(4)),
        edge.sourceId,
        edge.targetId,
        edge.layer,
        edge.linkCount,
      ]);
    }
    return { nodes, matrixData, maxValue };
  }, [graph, edgeLayers]);

  if (!graph) {
    return (
      <Paper
        variant="outlined"
        sx={{ minHeight: 520, borderRadius: 4, display: "grid", placeItems: "center" }}
      >
        Graph data is unavailable.
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ borderRadius: 4, p: 1.5 }}>
      <ReactECharts
        style={{ height: 560 }}
        option={{
          animation: false,
          grid: {
            left: 160,
            top: 40,
            right: 24,
            bottom: 120,
          },
          tooltip: {
            position: "top",
            formatter: (params: { data: [number, number, number, string, string, string, number] }) => {
              const [, , value, sourceId, targetId, layer, linkCount] = params.data;
              return [
                `<strong>${sourceId}</strong> → <strong>${targetId}</strong>`,
                `Layer: ${layer}`,
                `Weight: ${value}`,
                `Links: ${linkCount}`,
              ].join("<br/>");
            },
          },
          xAxis: {
            type: "category",
            data: nodes.map((node) => node.id),
            splitArea: { show: true },
            axisLabel: { rotate: 60, fontSize: 10 },
          },
          yAxis: {
            type: "category",
            data: nodes.map((node) => node.id),
            splitArea: { show: true },
            axisLabel: { fontSize: 10 },
          },
          visualMap: {
            min: 0,
            max: maxValue,
            calculable: true,
            orient: "horizontal",
            left: "center",
            bottom: 24,
            inRange: {
              color: ["#f6eee0", "#d28b36", "#12343b"],
            },
          },
          series: [
            {
              name: "Dependencies",
              type: "heatmap",
              data: matrixData,
              emphasis: {
                itemStyle: {
                  shadowBlur: 8,
                  shadowColor: "rgba(18, 52, 59, 0.28)",
                },
              },
            },
          ],
        }}
        onEvents={{
          click: (params: { data?: [number, number, number, string] }) => {
            const sourceId = params.data?.[3];
            if (sourceId) {
              onSelectOperation(sourceId);
            }
          },
        }}
      />
      {selectedOperationId ? (
        <div className="px-2 pb-1 pt-2 text-sm text-slate">
          Matrix focus: <span className="font-mono">{selectedOperationId}</span>
        </div>
      ) : null}
    </Paper>
  );
}
