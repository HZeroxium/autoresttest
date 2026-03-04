import { ButtonBase, Tooltip } from "@mui/material";

import { TraceChainItem } from "@/lib/schemas/api";

type TraceEventChipProps = {
  item: TraceChainItem;
  selected: boolean;
  onClick: () => void;
};

function colorForItem(item: TraceChainItem) {
  if (item.traceKind === "logical_request") {
    return { background: "#12343b", text: "#f5f2e9" };
  }
  if (item.traceKind === "llm_call") {
    return item.summaryLabel.includes("cache")
      ? { background: "#3b7a57", text: "#eef7ef" }
      : { background: "#49677c", text: "#eef3f7" };
  }
  if (item.isError) {
    return { background: "#a54730", text: "#fff4f1" };
  }
  return { background: "#d28b36", text: "#fff7ea" };
}

export function TraceEventChip({
  item,
  selected,
  onClick,
}: TraceEventChipProps) {
  const colors = colorForItem(item);
  return (
    <Tooltip title={item.summaryLabel} placement="top">
      <ButtonBase
        onClick={onClick}
        focusRipple
        sx={{
          minWidth: 86,
          borderRadius: 2.5,
          px: 1.25,
          py: 1,
          border: selected
            ? "2px solid rgba(18, 52, 59, 0.92)"
            : "1px solid rgba(18, 52, 59, 0.08)",
          backgroundColor: colors.background,
          color: colors.text,
          justifyContent: "flex-start",
          alignItems: "flex-start",
          textAlign: "left",
        }}
      >
        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">
            {item.traceKind.replace("_", " ")}
          </span>
          <span className="font-mono text-[11px]">#{item.eventSequenceId}</span>
          {typeof item.statusCode === "number" ? (
            <span className="text-[11px]">status {item.statusCode}</span>
          ) : null}
        </div>
      </ButtonBase>
    </Tooltip>
  );
}
