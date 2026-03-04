import { Activity } from "lucide-react";

import { useInspectorStore } from "@/lib/state/inspector-store";

export function LiveIndicator() {
  const liveMode = useInspectorStore((state) => state.liveMode);
  const setLiveMode = useInspectorStore((state) => state.setLiveMode);

  return (
    <button
      type="button"
      onClick={() => setLiveMode(!liveMode)}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition-colors ${
        liveMode
          ? "border-accent bg-accent text-white"
          : "border-line bg-paper text-slate"
      }`}
    >
      <Activity size={16} />
      {liveMode ? "Live polling on" : "Live polling off"}
    </button>
  );
}
