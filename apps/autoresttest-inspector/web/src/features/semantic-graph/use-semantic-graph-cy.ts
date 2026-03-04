import { RefObject, useEffect, useRef } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import type { Instance as TippyInstance } from "tippy.js";
import tippy from "tippy.js";

import "tippy.js/dist/tippy.css";

import { GraphSnapshot, OperationMetric } from "@/lib/schemas/api";
import { registerCytoscapePlugins } from "@/lib/cytoscape/register-plugins";

type GraphMetricMode = "structure" | "activity" | "errors" | "llm";
type GraphLabelDensity = "minimal" | "focused" | "all";
type GraphEdgeLayer = "effective" | "confirmed" | "tentative";

type UseSemanticGraphCyOptions = {
  graph?: GraphSnapshot;
  metricsByOperation: Record<string, OperationMetric>;
  selectedOperationId: string | null;
  edgeLayers: GraphEdgeLayer[];
  metricMode: GraphMetricMode;
  labelDensity: GraphLabelDensity;
  onSelectOperation: (operationId: string | null) => void;
};

const METHOD_COLORS: Record<string, string> = {
  GET: "#12343b",
  POST: "#2d6a4f",
  PUT: "#8f5f14",
  PATCH: "#b0672d",
  DELETE: "#a54730",
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function mixColor(from: string, to: string, ratio: number) {
  const safeRatio = clamp(ratio, 0, 1);
  const fromRgb = from
    .replace("#", "")
    .match(/.{1,2}/g)
    ?.map((chunk) => Number.parseInt(chunk, 16)) ?? [0, 0, 0];
  const toRgb =
    to
      .replace("#", "")
      .match(/.{1,2}/g)
      ?.map((chunk) => Number.parseInt(chunk, 16)) ?? [0, 0, 0];
  const mixed = fromRgb.map((value, index) =>
    Math.round(value + (toRgb[index] - value) * safeRatio),
  );
  return `#${mixed.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

function truncateLabel(value: string, maxLength = 38) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}…`;
}

function getNodeColor(
  node: GraphSnapshot["nodes"][number],
  metricMode: GraphMetricMode,
  metric: OperationMetric | undefined,
  maxActivity: number,
  maxLlm: number,
) {
  if (metricMode === "structure") {
    return METHOD_COLORS[node.method] ?? "#12343b";
  }

  if (metricMode === "activity") {
    const activity =
      (metric?.logicalCount ?? 0) +
      (metric?.httpAttemptCount ?? 0) +
      (metric?.llmCallCount ?? 0);
    const ratio = maxActivity > 0 ? activity / maxActivity : 0;
    return mixColor("#d9ebe6", "#12343b", ratio);
  }

  if (metricMode === "errors") {
    const errorCount =
      (metric?.clientError4xxCount ?? 0) +
      (metric?.serverError5xxCount ?? 0) +
      (metric?.transportErrorCount ?? 0);
    const base = metric?.httpAttemptCount ?? 0;
    const ratio = base > 0 ? errorCount / base : 0;
    return mixColor("#f3e6d5", "#a54730", ratio);
  }

  const llmCount = metric?.llmCallCount ?? 0;
  const ratio = maxLlm > 0 ? llmCount / maxLlm : 0;
  return mixColor("#dce9f4", "#49677c", ratio);
}

function buildElements(
  graph: GraphSnapshot,
  edgeLayers: GraphEdgeLayer[],
  metricMode: GraphMetricMode,
  metricsByOperation: Record<string, OperationMetric>,
): ElementDefinition[] {
  const groups = new Map<string, string>();
  for (const node of graph.nodes) {
    groups.set(node.resourceGroup, `group:${node.resourceGroup}`);
  }

  const maxActivity = Math.max(
    1,
    ...Object.values(metricsByOperation).map(
      (metric) =>
        metric.logicalCount + metric.httpAttemptCount + metric.llmCallCount,
    ),
  );
  const maxLlm = Math.max(
    1,
    ...Object.values(metricsByOperation).map((metric) => metric.llmCallCount),
  );

  const elements: ElementDefinition[] = Array.from(groups.entries()).map(
    ([groupLabel, groupId]) => ({
      data: {
        id: groupId,
        label: groupLabel,
        isGroup: true,
      },
      classes: "group-node",
    }),
  );

  for (const node of graph.nodes) {
    elements.push({
      data: {
        id: node.id,
        label: node.label,
        shortLabel: truncateLabel(`${node.method} ${node.path}`),
        operationId: node.id,
        method: node.method,
        path: node.path,
        parent: `group:${node.resourceGroup}`,
        fillColor: getNodeColor(
          node,
          metricMode,
          metricsByOperation[node.id],
          maxActivity,
          maxLlm,
        ),
        borderColor:
          (metricsByOperation[node.id]?.clientError4xxCount ?? 0) +
            (metricsByOperation[node.id]?.serverError5xxCount ?? 0) >
          0
            ? "#a54730"
            : "#12343b",
        size: clamp(18 + node.totalDegree * 3, 18, 38),
      },
      classes: "operation-node",
    });
  }

  for (const edge of graph.edges) {
    if (!edgeLayers.includes(edge.layer as GraphEdgeLayer)) {
      continue;
    }
    elements.push({
      data: {
        id: edge.id,
        source: edge.sourceId,
        target: edge.targetId,
        layer: edge.layer,
        weight: edge.maxSimilarity,
      },
      classes: `edge-${edge.layer}`,
    });
  }
  return elements;
}

function updatePresentation(
  cy: Core,
  selectedOperationId: string | null,
  labelDensity: GraphLabelDensity,
) {
  const operationNodes = cy.nodes(".operation-node");
  const groupNodes = cy.nodes(".group-node");
  const selectedNode = selectedOperationId
    ? cy.getElementById(selectedOperationId)
    : cy.collection();

  cy.batch(() => {
    operationNodes.removeClass("dimmed selected-node");
    groupNodes.removeClass("dimmed");
    cy.edges().removeClass("dimmed focused-edge");

    let visibleLabels = new Set<string>();
    if (labelDensity === "all") {
      visibleLabels = new Set(operationNodes.toArray().map((node) => node.id()));
    } else if (selectedNode.nonempty()) {
      visibleLabels.add(selectedNode.id());
      if (labelDensity === "focused") {
        selectedNode.neighborhood("node").forEach((node) => {
          visibleLabels.add(node.id());
        });
      }
    }

    operationNodes.forEach((node) => {
      node.data("displayLabel", visibleLabels.has(node.id()) ? node.data("shortLabel") : "");
    });

    if (selectedNode.nonempty()) {
      const neighborhood = selectedNode.closedNeighborhood();
      cy.elements().addClass("dimmed");
      neighborhood.removeClass("dimmed");
      groupNodes.forEach((groupNode) => {
        if (groupNode.children().intersection(neighborhood).nonempty()) {
          groupNode.removeClass("dimmed");
        }
      });
      selectedNode.addClass("selected-node");
      selectedNode.connectedEdges().addClass("focused-edge");
    }
  });
}

export function useSemanticGraphCy(
  containerRef: RefObject<HTMLDivElement | null>,
  {
    graph,
    metricsByOperation,
    selectedOperationId,
    edgeLayers,
    metricMode,
    labelDensity,
    onSelectOperation,
  }: UseSemanticGraphCyOptions,
) {
  const cyRef = useRef<Core | null>(null);
  const tooltipRef = useRef<TippyInstance | null>(null);

  useEffect(() => {
    registerCytoscapePlugins();
    const container = containerRef.current;
    if (!container || cyRef.current) {
      return;
    }

    const cy = cytoscape({
      container,
      minZoom: 0.35,
      maxZoom: 2.5,
      wheelSensitivity: 0.15,
      style: [
        {
          selector: "node",
          style: {
            label: "data(displayLabel)",
            "font-family": "IBM Plex Sans",
            "font-size": 10,
            color: "#12343b",
            "text-wrap": "wrap",
            "text-max-width": 180,
            "text-background-color": "#faf7ef",
            "text-background-opacity": 0.92,
            "text-background-padding": 4,
            "text-background-shape": "roundrectangle",
            "text-margin-y": -18,
          },
        },
        {
          selector: ".group-node",
          style: {
            "background-color": "rgba(18, 52, 59, 0.03)",
            "border-width": 1,
            "border-color": "rgba(18, 52, 59, 0.08)",
            shape: "roundrectangle",
            padding: 24,
            label: "",
          },
        },
        {
          selector: ".operation-node",
          style: {
            width: "data(size)",
            height: "data(size)",
            "background-color": "data(fillColor)",
            "border-color": "data(borderColor)",
            "border-width": 2,
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(weight, 0, 1, 1, 4)",
            "curve-style": "bezier",
            opacity: 0.48,
            "target-arrow-shape": "none",
          },
        },
        {
          selector: ".edge-effective",
          style: {
            "line-color": "#d28b36",
          },
        },
        {
          selector: ".edge-confirmed",
          style: {
            "line-color": "#7e8a8d",
            "line-style": "dashed",
          },
        },
        {
          selector: ".edge-tentative",
          style: {
            "line-color": "#b7c1c4",
            "line-style": "dotted",
          },
        },
        {
          selector: ".selected-node",
          style: {
            "border-width": 4,
            "border-color": "#d28b36",
          },
        },
        {
          selector: ".focused-edge",
          style: {
            opacity: 0.92,
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#d28b36",
          },
        },
        {
          selector: ".dimmed",
          style: {
            opacity: 0.12,
          },
        },
      ] as any,
    });

    cy.on("tap", (event) => {
      if (event.target === cy) {
        onSelectOperation(null);
      }
    });

    cy.on("tap", "node.operation-node", (event) => {
      onSelectOperation(String(event.target.data("operationId")));
    });

    cy.on("dbltap", "node.operation-node", (event) => {
      const node = event.target;
      const neighborhood = node.closedNeighborhood();
      cy.animate({
        fit: {
          eles: neighborhood,
          padding: 64,
        },
        duration: 180,
      });
    });

    cy.on("mouseover", "node.operation-node", (event) => {
      tooltipRef.current?.destroy();
      const node = event.target;
      const popperRef = (node as any).popperRef?.();
      if (!popperRef) {
        return;
      }

      const content = document.createElement("div");
      content.className = "rounded-xl border border-line bg-paper px-3 py-2 shadow-panel";
      const title = document.createElement("div");
      title.style.fontWeight = "600";
      title.style.marginBottom = "4px";
      title.textContent = String(node.data("shortLabel"));
      content.appendChild(title);
      const meta = document.createElement("div");
      meta.style.fontSize = "12px";
      meta.style.color = "#5f6f73";
      meta.textContent = `${String(node.data("method"))} • ${String(node.data("path"))}`;
      content.appendChild(meta);

      const dummy = document.createElement("div");
      document.body.appendChild(dummy);
      tooltipRef.current = tippy(dummy, {
        getReferenceClientRect: popperRef.getBoundingClientRect,
        content,
        trigger: "manual",
        appendTo: () => document.body,
        placement: "top",
        interactive: false,
      });
      tooltipRef.current.show();
    });

    cy.on("mouseout", "node.operation-node", () => {
      tooltipRef.current?.destroy();
      tooltipRef.current = null;
    });

    cyRef.current = cy;

    return () => {
      tooltipRef.current?.destroy();
      tooltipRef.current = null;
      cy.destroy();
      cyRef.current = null;
    };
  }, [containerRef, onSelectOperation]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !graph) {
      return;
    }

    cy.batch(() => {
      cy.elements().remove();
      cy.add(buildElements(graph, edgeLayers, metricMode, metricsByOperation));
    });

    cy.layout({
      name: "fcose",
      quality: "default",
      animate: false,
      fit: true,
      padding: 40,
      nodeRepulsion: 70000,
      idealEdgeLength: edgeLayers.length > 1 ? 110 : 92,
    } as never).run();

    updatePresentation(cy, selectedOperationId, labelDensity);
  }, [graph, edgeLayers, metricMode, metricsByOperation, selectedOperationId, labelDensity]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    updatePresentation(cy, selectedOperationId, labelDensity);
  }, [selectedOperationId, labelDensity]);
}
