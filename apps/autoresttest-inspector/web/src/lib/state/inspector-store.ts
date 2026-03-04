import { create } from "zustand";

type InspectorState = {
  selectedOperationId: string | null;
  selectedEventSequenceId: number | null;
  selectedLogicalRequestId: number | null;
  traceSearch: string;
  activeTab: string;
  liveMode: boolean;
  graphViewMode: "clustered" | "matrix";
  graphMetricMode: "structure" | "activity" | "errors" | "llm";
  graphEdgeLayers: Array<"effective" | "confirmed" | "tentative">;
  graphFocusMode: "full" | "neighbors";
  graphLabelDensity: "minimal" | "focused" | "all";
  selectedArtifact: string | null;
  baselineRunId: string | null;
  candidateRunId: string | null;
  setSelectedOperationId: (value: string | null) => void;
  setSelectedEventSequenceId: (value: number | null) => void;
  setSelectedLogicalRequestId: (value: number | null) => void;
  setTraceSearch: (value: string) => void;
  setActiveTab: (value: string) => void;
  setLiveMode: (value: boolean) => void;
  setGraphViewMode: (value: "clustered" | "matrix") => void;
  setGraphMetricMode: (
    value: "structure" | "activity" | "errors" | "llm",
  ) => void;
  setGraphEdgeLayers: (
    value: Array<"effective" | "confirmed" | "tentative">,
  ) => void;
  setGraphFocusMode: (value: "full" | "neighbors") => void;
  setGraphLabelDensity: (value: "minimal" | "focused" | "all") => void;
  setSelectedArtifact: (value: string | null) => void;
  setBaselineRunId: (value: string | null) => void;
  setCandidateRunId: (value: string | null) => void;
};

export const useInspectorStore = create<InspectorState>((set) => ({
  selectedOperationId: null,
  selectedEventSequenceId: null,
  selectedLogicalRequestId: null,
  traceSearch: "",
  activeTab: "overview",
  liveMode: true,
  graphViewMode: "clustered",
  graphMetricMode: "activity",
  graphEdgeLayers: ["effective"],
  graphFocusMode: "neighbors",
  graphLabelDensity: "focused",
  selectedArtifact: null,
  baselineRunId: null,
  candidateRunId: null,
  setSelectedOperationId: (value) => set({ selectedOperationId: value }),
  setSelectedEventSequenceId: (value) => set({ selectedEventSequenceId: value }),
  setSelectedLogicalRequestId: (value) =>
    set({ selectedLogicalRequestId: value }),
  setTraceSearch: (value) => set({ traceSearch: value }),
  setActiveTab: (value) => set({ activeTab: value }),
  setLiveMode: (value) => set({ liveMode: value }),
  setGraphViewMode: (value) => set({ graphViewMode: value }),
  setGraphMetricMode: (value) => set({ graphMetricMode: value }),
  setGraphEdgeLayers: (value) => set({ graphEdgeLayers: value }),
  setGraphFocusMode: (value) => set({ graphFocusMode: value }),
  setGraphLabelDensity: (value) => set({ graphLabelDensity: value }),
  setSelectedArtifact: (value) => set({ selectedArtifact: value }),
  setBaselineRunId: (value) => set({ baselineRunId: value }),
  setCandidateRunId: (value) => set({ candidateRunId: value }),
}));
