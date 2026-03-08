import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Autocomplete,
  Box,
  Chip,
  MenuItem,
  Slider,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import { TraceViewMode } from "./trace-grouping";

type FacetOption = {
  value: string;
  count: number;
};

type TraceViewControlsProps = {
  viewMode: TraceViewMode;
  operationOptions: FacetOption[];
  operationFilter: string | null;
  phaseOptions: FacetOption[];
  phaseFilter: string;
  search: string;
  traceKind: string;
  traceKindOptions: FacetOption[];
  statusCodeFilter: string;
  statusCodeOptions: FacetOption[];
  statusFamilyFilter: string;
  statusFamilyOptions: FacetOption[];
  llmPurposeFilter: string;
  llmPurposeOptions: FacetOption[];
  cacheHitFilter: string;
  requestFailedFilter: string;
  transportErrorFilter: string;
  durationRange: [number, number];
  maxDuration: number;
  eventCount: number;
  chainCount: number;
  onViewModeChange: (mode: TraceViewMode) => void;
  onOperationFilterChange: (value: string | null) => void;
  onPhaseFilterChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onTraceKindChange: (value: string) => void;
  onStatusCodeFilterChange: (value: string) => void;
  onStatusFamilyFilterChange: (value: string) => void;
  onLlmPurposeFilterChange: (value: string) => void;
  onCacheHitFilterChange: (value: string) => void;
  onRequestFailedFilterChange: (value: string) => void;
  onTransportErrorFilterChange: (value: string) => void;
  onDurationRangeChange: (value: [number, number]) => void;
};

export function TraceViewControls({
  viewMode,
  operationOptions,
  operationFilter,
  phaseOptions,
  phaseFilter,
  search,
  traceKind,
  traceKindOptions,
  statusCodeFilter,
  statusCodeOptions,
  statusFamilyFilter,
  statusFamilyOptions,
  llmPurposeFilter,
  llmPurposeOptions,
  cacheHitFilter,
  requestFailedFilter,
  transportErrorFilter,
  durationRange,
  maxDuration,
  eventCount,
  chainCount,
  onViewModeChange,
  onOperationFilterChange,
  onPhaseFilterChange,
  onSearchChange,
  onTraceKindChange,
  onStatusCodeFilterChange,
  onStatusFamilyFilterChange,
  onLlmPurposeFilterChange,
  onCacheHitFilterChange,
  onRequestFailedFilterChange,
  onTransportErrorFilterChange,
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
          <Chip label={`${eventCount} filtered events`} />
          <Chip label={`${chainCount} loaded sequences`} variant="outlined" />
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
                getOptionLabel={(option) =>
                  typeof option === "string"
                    ? option
                    : `${option.value} (${option.count})`
                }
                value={
                  operationFilter
                    ? operationOptions.find((option) => option.value === operationFilter) ?? null
                    : null
                }
                onChange={(_, value) =>
                  onOperationFilterChange(typeof value === "string" ? value : value?.value ?? null)
                }
                renderInput={(params) => (
                  <TextField {...params} label="Operation filter" />
                )}
              />
              <TextField
                size="small"
                label="Search payload"
                value={search}
                onChange={(event) => onSearchChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", xl: 240 } }}
              />
              <TextField
                select
                size="small"
                label="Trace kind"
                value={traceKind}
                onChange={(event) => onTraceKindChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 180 } }}
              >
                <MenuItem value="">All trace kinds</MenuItem>
                {traceKindOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.value} ({option.count})
                  </MenuItem>
                ))}
              </TextField>
            </Stack>

            <Stack
              direction={{ xs: "column", xl: "row" }}
              spacing={1.5}
              useFlexGap
              sx={{ alignItems: { xl: "center" } }}
            >
              <TextField
                select
                size="small"
                label="Phase"
                value={phaseFilter}
                onChange={(event) => onPhaseFilterChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 200 } }}
              >
                <MenuItem value="">All phases</MenuItem>
                {phaseOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.value} ({option.count})
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="Status code"
                value={statusCodeFilter}
                onChange={(event) => onStatusCodeFilterChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 180 } }}
              >
                <MenuItem value="">All status codes</MenuItem>
                {statusCodeOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.value} ({option.count})
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="Status family"
                value={statusFamilyFilter}
                onChange={(event) => onStatusFamilyFilterChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 180 } }}
              >
                <MenuItem value="">All status families</MenuItem>
                {statusFamilyOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.value} ({option.count})
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="LLM purpose"
                value={llmPurposeFilter}
                onChange={(event) => onLlmPurposeFilterChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 200 } }}
              >
                <MenuItem value="">All LLM purposes</MenuItem>
                {llmPurposeOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.value} ({option.count})
                  </MenuItem>
                ))}
              </TextField>
            </Stack>

            <Stack
              direction={{ xs: "column", xl: "row" }}
              spacing={1.5}
              useFlexGap
            >
              <TextField
                select
                size="small"
                label="Cache hit"
                value={cacheHitFilter}
                onChange={(event) => onCacheHitFilterChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 180 } }}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="true">Only cache hits</MenuItem>
                <MenuItem value="false">Only non-cache hits</MenuItem>
              </TextField>
              <TextField
                select
                size="small"
                label="Request failed"
                value={requestFailedFilter}
                onChange={(event) => onRequestFailedFilterChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 180 } }}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="true">Only failed</MenuItem>
                <MenuItem value="false">Only not failed</MenuItem>
              </TextField>
              <TextField
                select
                size="small"
                label="Transport error"
                value={transportErrorFilter}
                onChange={(event) => onTransportErrorFilterChange(event.target.value)}
                sx={{ minWidth: { xs: "100%", md: 180 } }}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="true">Only transport errors</MenuItem>
                <MenuItem value="false">Only HTTP responses</MenuItem>
              </TextField>
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
