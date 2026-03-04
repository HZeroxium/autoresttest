import type { PropsWithChildren } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DatasetDashboard } from "@/features/dataset-browser/dataset-dashboard";
import { DatasetSummary } from "@/lib/schemas/api";

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    ...props
  }: PropsWithChildren<Record<string, unknown>>) => <a {...props}>{children}</a>,
}));

describe("DatasetDashboard", () => {
  it("renders dataset summary cards", () => {
    const datasets: DatasetSummary[] = [
      {
        datasetId: "Bills-api",
        displayName: "Bills api",
        hasDataArtifacts: true,
        hasRuntimeManifests: true,
        hasTraceArtifacts: true,
        hasGraphCache: true,
        hasQtableCache: true,
        latestRunId: "Bills-api-20260304T152803Z-3764",
        latestRunStatus: "completed",
        latestUpdatedAt: "2026-03-04T15:29:13.304963Z",
      },
    ];

    render(<DatasetDashboard datasets={datasets} />);

    expect(screen.getByText("Bills-api")).toBeInTheDocument();
    expect(screen.getByText(/Latest run:/i)).toHaveTextContent(
      "Latest run: Bills-api-20260304T152803Z-3764",
    );
    expect(screen.getByText("Open dataset")).toBeInTheDocument();
  });
});
