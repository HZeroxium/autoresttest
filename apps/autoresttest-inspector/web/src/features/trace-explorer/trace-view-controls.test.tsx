import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TraceViewControls } from "@/features/trace-explorer/trace-view-controls";

describe("TraceViewControls", () => {
  it("renders the extended server-side filters", () => {
    render(
      <TraceViewControls
        viewMode="story"
        operationOptions={[{ value: "opA", count: 3 }]}
        operationFilter={null}
        phaseOptions={[{ value: "exploration", count: 4 }]}
        phaseFilter=""
        search=""
        traceKind=""
        traceKindOptions={[{ value: "llm_call", count: 2 }]}
        statusCodeFilter=""
        statusCodeOptions={[{ value: "503", count: 1 }]}
        statusFamilyFilter=""
        statusFamilyOptions={[{ value: "5xx", count: 1 }]}
        llmPurposeFilter=""
        llmPurposeOptions={[{ value: "repair_generation", count: 1 }]}
        cacheHitFilter="all"
        requestFailedFilter="all"
        transportErrorFilter="all"
        durationRange={[0, 5000]}
        maxDuration={5000}
        eventCount={10}
        chainCount={3}
        onViewModeChange={vi.fn()}
        onOperationFilterChange={vi.fn()}
        onPhaseFilterChange={vi.fn()}
        onSearchChange={vi.fn()}
        onTraceKindChange={vi.fn()}
        onStatusCodeFilterChange={vi.fn()}
        onStatusFamilyFilterChange={vi.fn()}
        onLlmPurposeFilterChange={vi.fn()}
        onCacheHitFilterChange={vi.fn()}
        onRequestFailedFilterChange={vi.fn()}
        onTransportErrorFilterChange={vi.fn()}
        onDurationRangeChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Filters and analysis lens")).toBeInTheDocument();
    expect(screen.getByLabelText("Status code")).toBeInTheDocument();
    expect(screen.getByLabelText("Status family")).toBeInTheDocument();
    expect(screen.getByLabelText("LLM purpose")).toBeInTheDocument();
    expect(screen.getByLabelText("Cache hit")).toBeInTheDocument();
    expect(screen.getByLabelText("Request failed")).toBeInTheDocument();
    expect(screen.getByLabelText("Transport error")).toBeInTheDocument();
    expect(screen.getByText(/Event duration filter/i)).toBeInTheDocument();
  });
});
