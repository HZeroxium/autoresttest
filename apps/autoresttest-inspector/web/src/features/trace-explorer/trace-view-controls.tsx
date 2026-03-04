import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Autocomplete,
  Box,
  Chip,
  FormControlLabel,
  Slider,
  Stack,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import { TraceViewMode } from "./trace-grouping";

type TraceViewControlsProps = {
  viewMode: TraceViewMode;
  operationOptions: string[];
  operationFilter: string | null;
  search: string;
  traceKind: string;
  phaseFilters: string[];
  phases: string[];
  errorsOnly: boolean;
  retriesOnly: boolean;
  durationRange: [number, number];
  maxDuration: number;
  eventCount: number;
  chainCount: number;
  onViewModeChange: (mode: TraceViewMode) => void;
  onOperationFilterChange: (value: string | null) => void;
  onSearchChange: (value: string) => void;
  onTraceKindChange: (value: string) => void;
  onTogglePhase: (phase: string) => void;
  onErrorsOnlyChange: (value: boolean) => void;
  onRetriesOnlyChange: (value: boolean) => void;
  onDurationRangeChange: (value: [number, number]) => void;
};

export function TraceViewControls({
  viewMode,
  operationOptions,
  operationFilter,
  search,
  traceKind,
  phaseFilters,
  phases,
  errorsOnly,
  retriesOnly,
  durationRange,
  maxDuration,
  eventCount,
  chainCount,
  onViewModeChange,
  onOperationFilterChange,
  onSearchChange,
  onTraceKindChange,
  onTogglePhase,
  onErrorsOnlyChange,
  onRetriesOnlyChange,
  onDurationRangeChange,
}: TraceViewControlsProps) {
  return (
    <Stack spacing={2}>
      <Stack
        direction={{ xs: "column", lg: "row" }}
        spacing={1.5}
        useFlexGap
        sx={{ alignItems: { lg: "center" }, justifyContent: "space-between" }}
      >
        <ToggleButtonGroup
          exclusive
          size="small"
          value={viewMode}
          onChange={(_, value: TraceViewMode | null) => {
            if (value) {
              onViewModeChange(value);
            }
          }}
          sx={{
            flexWrap: "wrap",
            "& .MuiToggleButton-root": {
              px: 1.5,
              py: 0.85,
            },
          }}
        >
          <ToggleButton value="story">Sequence Story</ToggleButton>
          <ToggleButton value="swimlanes">Phase Swimlanes</ToggleButton>
          <ToggleButton value="ribbon">Sequence Ribbon</ToggleButton>
          <ToggleButton value="cards">Chain Cards</ToggleButton>
          <ToggleButton value="ledger">Event Ledger</ToggleButton>
        </ToggleButtonGroup>

        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          <Chip label={`${eventCount} events`} />
          <Chip label={`${chainCount} sequences`} variant="outlined" />
        </Stack>
      </Stack>

      <Accordion disableGutters defaultExpanded sx={{ borderRadius: 4, overflow: "hidden" }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2">Filters and analysis lens</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={2.5}>
            <Stack
              direction={{ xs: "column", xl: "row" }}
              spacing={1.5}
              useFlexGap
              sx={{ alignItems: { xl: "center" } }}
            >
              <Autocomplete
                size="small"
                sx={{ minWidth: { xs: "100%", xl: 320 } }}
                options={operationOptions}
                value={operationFilter}
                onChange={(_, value) => onOperationFilterChange(value)}
                renderInput={(params) => (
                  <TextField {...params} label="Operation filter" />
                )}
              />
              <TextField
                size="small"
                label="Search"
                value={search}
                onChange={(event) => onSearchChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", xl: 260 } }}
              />
              <ToggleButtonGroup
                exclusive
                size="small"
                value={traceKind}
                onChange={(_, value: string | null) => onTraceKindChange(value ?? "")}
              >
                <ToggleButton value="">All traces</ToggleButton>
                <ToggleButton value="logical_request">Logical</ToggleButton>
                <ToggleButton value="http_attempt">HTTP</ToggleButton>
                <ToggleButton value="llm_call">LLM</ToggleButton>
              </ToggleButtonGroup>
            </Stack>

            <Stack
              direction={{ xs: "column", xl: "row" }}
              spacing={2}
              useFlexGap
              sx={{ alignItems: { xl: "center" }, justifyContent: "space-between" }}
            >
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                {phases.map((phase) => {
                  const active = phaseFilters.includes(phase);
                  return (
                    <Chip
                      key={phase}
                      label={phase}
                      clickable
                      color={active ? "secondary" : "default"}
                      variant={active ? "filled" : "outlined"}
                      onClick={() => onTogglePhase(phase)}
                    />
                  );
                })}
              </Box>

              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={errorsOnly}
                      onChange={(event) => onErrorsOnlyChange(event.target.checked)}
                    />
                  }
                  label="Errors only"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={retriesOnly}
                      onChange={(event) => onRetriesOnlyChange(event.target.checked)}
                    />
                  }
                  label="Retries only"
                />
              </Stack>
            </Stack>

            <Box sx={{ px: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Event duration filter ({Math.round(durationRange[0])} ms to{" "}
                {Math.round(durationRange[1])} ms)
              </Typography>
              <Slider
                min={0}
                max={Math.max(1000, maxDuration)}
                value={durationRange}
                onChange={(_, value) => onDurationRangeChange(value as [number, number])}
                valueLabelDisplay="auto"
              />
            </Box>
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Stack>
  );
}
