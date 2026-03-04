import {
  Button,
  Chip,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import { GraphNode, OperationMetric } from "@/lib/schemas/api";
import { formatCompactNumber, formatNumber } from "@/lib/formatters/format";

type SemanticGraphInspectorProps = {
  selectedNode?: GraphNode;
  selectedMetric?: OperationMetric;
  inboundNeighbors: GraphNode[];
  outboundNeighbors: GraphNode[];
  onSelectOperation: (operationId: string | null) => void;
  onOpenTraces: () => void;
};

function NeighborSection({
  label,
  nodes,
  onSelectOperation,
}: {
  label: string;
  nodes: GraphNode[];
  onSelectOperation: (operationId: string | null) => void;
}) {
  return (
    <Stack spacing={1.25}>
      <Typography variant="subtitle2">{label}</Typography>
      <Stack direction="row" flexWrap="wrap" gap={1}>
        {nodes.length > 0 ? (
          nodes.map((node) => (
            <Chip
              key={node.id}
              label={`${node.method} ${node.path}`}
              onClick={() => onSelectOperation(node.id)}
              variant="outlined"
            />
          ))
        ) : (
          <Typography variant="body2" color="text.secondary">
            None
          </Typography>
        )}
      </Stack>
    </Stack>
  );
}

export function SemanticGraphInspector({
  selectedNode,
  selectedMetric,
  inboundNeighbors,
  outboundNeighbors,
  onSelectOperation,
  onOpenTraces,
}: SemanticGraphInspectorProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2.5,
        height: "100%",
        position: "sticky",
        top: 0,
        borderRadius: 4,
        backgroundColor: "background.paper",
      }}
    >
      {selectedNode ? (
        <Stack spacing={2}>
          <div>
            <Typography variant="overline" color="text.secondary">
              Operation
            </Typography>
            <Typography variant="h6">{selectedNode.id}</Typography>
            <Typography variant="body2" color="text.secondary">
              {selectedNode.method} {selectedNode.path}
            </Typography>
          </div>

          <Stack direction="row" flexWrap="wrap" gap={1}>
            <Chip label={`Group: ${selectedNode.resourceGroup}`} />
            <Chip
              variant="outlined"
              label={`Degree ${selectedNode.inDegree}/${selectedNode.outDegree}`}
            />
            <Chip
              variant="outlined"
              label={`${selectedNode.requiredParameterCount}/${selectedNode.parameterCount} required`}
            />
          </Stack>

          <Divider />

          <Stack direction="row" spacing={1.5}>
            <MetricCard
              label="Logical"
              value={formatNumber(selectedMetric?.logicalCount)}
            />
            <MetricCard
              label="HTTP"
              value={formatNumber(selectedMetric?.httpAttemptCount)}
            />
            <MetricCard
              label="LLM"
              value={formatNumber(selectedMetric?.llmCallCount)}
            />
          </Stack>
          <Stack direction="row" spacing={1.5}>
            <MetricCard
              label="Retries"
              value={formatNumber(selectedMetric?.retryCount)}
            />
            <MetricCard
              label="2xx"
              value={formatNumber(selectedMetric?.success2xxCount)}
            />
            <MetricCard
              label="Errors"
              value={formatNumber(
                (selectedMetric?.clientError4xxCount ?? 0) +
                  (selectedMetric?.serverError5xxCount ?? 0) +
                  (selectedMetric?.transportErrorCount ?? 0),
              )}
            />
          </Stack>

          <Stack spacing={0.5}>
            <Typography variant="subtitle2">Timing</Typography>
            <Typography variant="body2" color="text.secondary">
              Avg {formatCompactNumber(selectedMetric?.avgDurationMs)} ms
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Max {formatCompactNumber(selectedMetric?.maxDurationMs)} ms
            </Typography>
          </Stack>

          <Divider />

          <NeighborSection
            label="Upstream neighbors"
            nodes={inboundNeighbors}
            onSelectOperation={onSelectOperation}
          />
          <NeighborSection
            label="Downstream neighbors"
            nodes={outboundNeighbors}
            onSelectOperation={onSelectOperation}
          />

          <Divider />

          <Stack direction="row" spacing={1.25} useFlexGap flexWrap="wrap">
            <Button
              variant="outlined"
              disabled={inboundNeighbors.length === 0}
              onClick={() => onSelectOperation(inboundNeighbors[0]?.id ?? null)}
            >
              Focus upstream
            </Button>
            <Button
              variant="outlined"
              disabled={outboundNeighbors.length === 0}
              onClick={() => onSelectOperation(outboundNeighbors[0]?.id ?? null)}
            >
              Focus downstream
            </Button>
            <Button variant="contained" color="secondary" onClick={onOpenTraces}>
              Open traces
            </Button>
          </Stack>
        </Stack>
      ) : (
        <Stack spacing={1.5}>
          <Typography variant="h6">Operation inspector</Typography>
          <Typography variant="body2" color="text.secondary">
            Select a node to focus its neighborhood, inspect runtime activity, and
            jump directly into trace chains for that operation.
          </Typography>
        </Stack>
      )}
    </Paper>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        px: 1.5,
        py: 1.25,
        flex: 1,
        borderRadius: 3,
        backgroundColor: "rgba(245, 242, 233, 0.65)",
      }}
    >
      <Typography variant="overline" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="subtitle1">{value}</Typography>
    </Paper>
  );
}
