import { useMemo, useRef } from "react";
import { Stack } from "@mui/material";

import { Panel } from "@/components/common/panel";
import { useOperationMetrics } from "@/lib/api/hooks";
import { GraphSnapshot } from "@/lib/schemas/api";
import { useInspectorStore } from "@/lib/state/inspector-store";

import { DependencyMatrix } from "./dependency-matrix";
import { SemanticGraphControls } from "./semantic-graph-controls";
import { SemanticGraphInspector } from "./semantic-graph-inspector";
import { useSemanticGraphCy } from "./use-semantic-graph-cy";

type SemanticGraphPanelProps = {
  datasetId: string;
  runId: string;
  graph?: GraphSnapshot;
};

export function SemanticGraphPanel({
  datasetId,
  runId,
  graph,
}: SemanticGraphPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const metricsQuery = useOperationMetrics(datasetId, runId);

  const selectedOperationId = useInspectorStore((state) => state.selectedOperationId);
  const setSelectedOperationId = useInspectorStore(
    (state) => state.setSelectedOperationId,
  );
  const setSelectedLogicalRequestId = useInspectorStore(
    (state) => state.setSelectedLogicalRequestId,
  );
  const setSelectedEventSequenceId = useInspectorStore(
    (state) => state.setSelectedEventSequenceId,
  );
  const setActiveTab = useInspectorStore((state) => state.setActiveTab);
  const graphViewMode = useInspectorStore((state) => state.graphViewMode);
  const setGraphViewMode = useInspectorStore((state) => state.setGraphViewMode);
  const graphMetricMode = useInspectorStore((state) => state.graphMetricMode);
  const setGraphMetricMode = useInspectorStore((state) => state.setGraphMetricMode);
  const graphEdgeLayers = useInspectorStore((state) => state.graphEdgeLayers);
  const setGraphEdgeLayers = useInspectorStore((state) => state.setGraphEdgeLayers);
  const graphLabelDensity = useInspectorStore((state) => state.graphLabelDensity);
  const setGraphLabelDensity = useInspectorStore(
    (state) => state.setGraphLabelDensity,
  );
  const setGraphFocusMode = useInspectorStore((state) => state.setGraphFocusMode);

  const metricsByOperation = useMemo(
    () =>
      Object.fromEntries(
        (metricsQuery.data?.operations ?? []).map((metric) => [metric.operationId, metric]),
      ),
    [metricsQuery.data?.operations],
  );

  const selectedNode =
    graph?.nodes.find((node) => node.id === selectedOperationId) ?? undefined;

  const selectedMetric = selectedNode
    ? metricsByOperation[selectedNode.id]
    : undefined;

  const inboundNeighbors = useMemo(() => {
    if (!graph || !selectedNode) {
      return [];
    }
    const inboundIds = new Set(
      graph.edges
        .filter(
          (edge) =>
            graphEdgeLayers.includes(edge.layer as never) &&
            edge.targetId === selectedNode.id,
        )
        .map((edge) => edge.sourceId),
    );
    return graph.nodes.filter((node) => inboundIds.has(node.id));
  }, [graph, selectedNode, graphEdgeLayers]);

  const outboundNeighbors = useMemo(() => {
    if (!graph || !selectedNode) {
      return [];
    }
    const outboundIds = new Set(
      graph.edges
        .filter(
          (edge) =>
            graphEdgeLayers.includes(edge.layer as never) &&
            edge.sourceId === selectedNode.id,
        )
        .map((edge) => edge.targetId),
    );
    return graph.nodes.filter((node) => outboundIds.has(node.id));
  }, [graph, selectedNode, graphEdgeLayers]);

  useSemanticGraphCy(containerRef, {
    graph: graphViewMode === "clustered" ? graph : undefined,
    metricsByOperation,
    selectedOperationId,
    edgeLayers: graphEdgeLayers,
    metricMode: graphMetricMode,
    labelDensity: graphLabelDensity,
    onSelectOperation: (operationId) => {
      setSelectedOperationId(operationId);
      setSelectedLogicalRequestId(null);
      setSelectedEventSequenceId(null);
      setGraphFocusMode(operationId ? "neighbors" : "full");
    },
  });

  return (
    <div className="space-y-4">
      <Panel title="Semantic dependency graph">
        <SemanticGraphControls
          graph={graph}
          graphViewMode={graphViewMode}
          graphMetricMode={graphMetricMode}
          graphEdgeLayers={graphEdgeLayers}
          showAllLabels={graphLabelDensity === "all"}
          selectedOperationId={selectedOperationId}
          onGraphViewModeChange={setGraphViewMode}
          onGraphMetricModeChange={setGraphMetricMode}
          onGraphEdgeLayersChange={setGraphEdgeLayers}
          onShowAllLabelsChange={(value) =>
            setGraphLabelDensity(value ? "all" : "focused")
          }
          onSelectOperation={(operationId) => {
            setSelectedOperationId(operationId);
            setSelectedLogicalRequestId(null);
            setSelectedEventSequenceId(null);
            setGraphFocusMode(operationId ? "neighbors" : "full");
          }}
          onResetFocus={() => {
            setSelectedOperationId(null);
            setSelectedLogicalRequestId(null);
            setSelectedEventSequenceId(null);
            setGraphFocusMode("full");
          }}
        />
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_380px]">
        <Panel
          title={
            graphViewMode === "clustered" ? "Clustered map" : "Dependency matrix"
          }
          className="min-h-[640px]"
        >
          {graphViewMode === "clustered" ? (
            <div ref={containerRef} className="h-[560px] w-full rounded-3xl bg-paper" />
          ) : (
            <DependencyMatrix
              graph={graph}
              edgeLayers={graphEdgeLayers}
              selectedOperationId={selectedOperationId}
              onSelectOperation={(operationId) => {
                setSelectedOperationId(operationId);
                setSelectedLogicalRequestId(null);
                setSelectedEventSequenceId(null);
                setGraphFocusMode(operationId ? "neighbors" : "full");
              }}
            />
          )}
        </Panel>

        <Stack spacing={2}>
          <SemanticGraphInspector
            selectedNode={selectedNode}
            selectedMetric={selectedMetric}
            inboundNeighbors={inboundNeighbors}
            outboundNeighbors={outboundNeighbors}
            onSelectOperation={(operationId) => {
              setSelectedOperationId(operationId);
              setSelectedLogicalRequestId(null);
              setSelectedEventSequenceId(null);
              setGraphFocusMode(operationId ? "neighbors" : "full");
            }}
            onOpenTraces={() => setActiveTab("traces")}
          />
        </Stack>
      </div>
    </div>
  );
}
