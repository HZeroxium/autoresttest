import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ArtifactsPanel } from "@/features/artifacts-browser/artifacts-panel";
import * as apiHooks from "@/lib/api/hooks";
import { ArtifactsResponse } from "@/lib/schemas/api";
import { useInspectorStore } from "@/lib/state/inspector-store";

vi.mock("@/lib/api/hooks", () => ({
  useArtifactPayload: vi.fn(),
  useArtifactPreview: vi.fn(),
}));

describe("ArtifactsPanel", () => {
  beforeEach(() => {
    useInspectorStore.setState({ selectedArtifact: null });
    vi.clearAllMocks();
  });

  it("uses preview mode by default and loads raw payload on demand", async () => {
    const previewMock = vi.mocked(apiHooks.useArtifactPreview);
    const payloadMock = vi.mocked(apiHooks.useArtifactPayload);
    const artifacts: ArtifactsResponse = {
      datasetId: "demo",
      runId: "demo-20260305T000000Z-1000",
      artifacts: [
        {
          name: "report.json",
          available: true,
          sizeBytes: 256,
          itemCount: 4,
        },
        {
          name: "successful_responses.json",
          available: true,
          sizeBytes: 1024,
          itemCount: 2,
        },
      ],
    };

    previewMock.mockImplementation(
      ((_datasetId, _runId, artifactName) =>
        ({
          data:
            artifactName == null
              ? undefined
              : {
                  datasetId: "demo",
                  runId: "demo-20260305T000000Z-1000",
                  artifactName,
                  summary: {
                    topLevelType: "dict",
                    totalItems: 2,
                  },
                  offset: 0,
                  limit: 40,
                  total: 2,
                  hasMore: false,
                  entries: [
                    {
                      key: "opA",
                      valueType: "array",
                      itemCount: 2,
                      preview: {
                        firstItem: { status: 200 },
                      },
                    },
                  ],
                  warnings: [],
                },
          isLoading: false,
        }) as any),
    );
    payloadMock.mockImplementation(
      ((_datasetId, _runId, artifactName) =>
        ({
          data:
            artifactName == null
              ? undefined
              : {
                  datasetId: "demo",
                  runId: "demo-20260305T000000Z-1000",
                  artifactName,
                  payload: { raw: true },
                },
          isLoading: false,
        }) as any),
    );

    render(
      <ArtifactsPanel
        datasetId="demo"
        runId="demo-20260305T000000Z-1000"
        artifacts={artifacts}
      />,
    );

    await waitFor(() =>
      expect(previewMock).toHaveBeenLastCalledWith(
        "demo",
        "demo-20260305T000000Z-1000",
        "report.json",
        expect.objectContaining({ enabled: true, limit: 40 }),
      ),
    );
    expect(payloadMock).toHaveBeenLastCalledWith(
      "demo",
      "demo-20260305T000000Z-1000",
      undefined,
    );
    expect(screen.getByText("Preview entries")).toBeInTheDocument();
    expect(screen.getByText("opA")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Raw JSON" }));

    await waitFor(() =>
      expect(payloadMock).toHaveBeenLastCalledWith(
        "demo",
        "demo-20260305T000000Z-1000",
        "report.json",
      ),
    );
    expect(screen.getByText(/"raw": true/)).toBeInTheDocument();
  });
});
