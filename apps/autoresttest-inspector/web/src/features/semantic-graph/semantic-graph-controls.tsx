import {
  Autocomplete,
  Box,
  Button,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";

import { GraphSnapshot } from "@/lib/schemas/api";

type GraphMetricMode = "structure" | "activity" | "errors" | "llm";
type GraphViewMode = "clustered" | "matrix";
type GraphEdgeLayer = "effective" | "confirmed" | "tentative";

type SemanticGraphControlsProps = {
  graph?: GraphSnapshot;
  graphViewMode: GraphViewMode;
  graphMetricMode: GraphMetricMode;
  graphEdgeLayers: GraphEdgeLayer[];
  showAllLabels: boolean;
  selectedOperationId: string | null;
  onGraphViewModeChange: (value: GraphViewMode) => void;
  onGraphMetricModeChange: (value: GraphMetricMode) => void;
  onGraphEdgeLayersChange: (value: GraphEdgeLayer[]) => void;
  onShowAllLabelsChange: (value: boolean) => void;
  onSelectOperation: (value: string | null) => void;
  onResetFocus: () => void;
};

export function SemanticGraphControls({
  graph,
  graphViewMode,
  graphMetricMode,
  graphEdgeLayers,
  showAllLabels,
  selectedOperationId,
  onGraphViewModeChange,
  onGraphMetricModeChange,
  onGraphEdgeLayersChange,
  onShowAllLabelsChange,
  onSelectOperation,
  onResetFocus,
}: SemanticGraphControlsProps) {
  return (
    <Stack spacing={2}>
      <Stack
        direction={{ xs: "column", lg: "row" }}
        spacing={1.5}
        useFlexGap
        sx={{ alignItems: { lg: "center" }, justifyContent: "space-between" }}
      >
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} useFlexGap>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={graphViewMode}
            onChange={(_, value: GraphViewMode | null) => {
              if (value) {
                onGraphViewModeChange(value);
              }
            }}
          >
            <ToggleButton value="clustered">Clustered Map</ToggleButton>
            <ToggleButton value="matrix">Dependency Matrix</ToggleButton>
          </ToggleButtonGroup>

          <ToggleButtonGroup
            exclusive
            size="small"
            value={graphMetricMode}
            onChange={(_, value: GraphMetricMode | null) => {
              if (value) {
                onGraphMetricModeChange(value);
              }
            }}
          >
            <ToggleButton value="structure">Structure</ToggleButton>
            <ToggleButton value="activity">Activity</ToggleButton>
            <ToggleButton value="errors">Errors</ToggleButton>
            <ToggleButton value="llm">LLM</ToggleButton>
          </ToggleButtonGroup>
        </Stack>

        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} useFlexGap>
          <Autocomplete
            size="small"
            sx={{ minWidth: 280 }}
            options={graph?.nodes ?? []}
            value={
              graph?.nodes.find((node) => node.id === selectedOperationId) ?? null
            }
            getOptionLabel={(option) => `${option.method} ${option.path}`}
            onChange={(_, value) => onSelectOperation(value?.id ?? null)}
            renderInput={(params) => (
              <TextField {...params} label="Jump to operation" />
            )}
          />
          <Button variant="outlined" onClick={onResetFocus}>
            Reset focus
          </Button>
        </Stack>
      </Stack>

      <Stack
        direction={{ xs: "column", lg: "row" }}
        spacing={1.5}
        useFlexGap
        sx={{ alignItems: { lg: "center" }, justifyContent: "space-between" }}
      >
        <ToggleButtonGroup
          size="small"
          value={graphEdgeLayers}
          onChange={(_, value: GraphEdgeLayer[]) => {
            if (value.length > 0) {
              onGraphEdgeLayersChange(value);
            }
          }}
        >
          <ToggleButton value="effective">Effective</ToggleButton>
          <ToggleButton value="confirmed">Confirmed</ToggleButton>
          <ToggleButton value="tentative">Tentative</ToggleButton>
        </ToggleButtonGroup>

        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <FormControlLabel
            control={
              <Switch
                checked={showAllLabels}
                onChange={(event) => onShowAllLabelsChange(event.target.checked)}
              />
            }
            label="Show all labels"
          />
        </Box>
      </Stack>
    </Stack>
  );
}
