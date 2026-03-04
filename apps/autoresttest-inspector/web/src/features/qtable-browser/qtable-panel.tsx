import { useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import ReactECharts from "echarts-for-react";

import { Panel } from "@/components/common/panel";
import { CacheQTableSnapshot, QTableSnapshot } from "@/lib/schemas/api";
import { formatNumber } from "@/lib/formatters/format";

type QTablePanelProps = {
  runtimeQtables?: QTableSnapshot;
  cachedQtables?: CacheQTableSnapshot;
};

type AgentRow = {
  agentName: string;
  entryCount: number;
  nonZeroCount: number;
  minValue?: number | null;
  maxValue?: number | null;
  meanValue: number | null | undefined;
  sparsityRatio: number;
};

export function QTablePanel({ runtimeQtables, cachedQtables }: QTablePanelProps) {
  const [search, setSearch] = useState("");
  const rows = (runtimeQtables?.agentSummaries ?? []) as AgentRow[];

  const filteredOperations = useMemo(() => {
    const operationEntries = Object.entries(runtimeQtables?.operations ?? {});
    return operationEntries.filter(([operationId]) =>
      operationId.toLowerCase().includes(search.toLowerCase()),
    );
  }, [runtimeQtables, search]);

  const columns = useMemo<ColumnDef<AgentRow>[]>(
    () => [
      { accessorKey: "agentName", header: "Agent" },
      { accessorKey: "entryCount", header: "Entries" },
      { accessorKey: "nonZeroCount", header: "Non-zero" },
      {
        accessorKey: "meanValue",
        header: "Mean",
        cell: (info) =>
          typeof info.getValue() === "number"
            ? (info.getValue() as number).toFixed(4)
            : "n/a",
      },
      {
        accessorKey: "sparsityRatio",
        header: "Sparsity",
        cell: (info) => `${((info.getValue() as number) * 100).toFixed(1)}%`,
      },
    ],
    [],
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Panel title="Agent summaries">
          <div className="overflow-hidden rounded-2xl border border-line">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-paper text-slate">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th key={header.id} className="px-3 py-3 font-medium">
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="border-t border-line bg-white">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-3">
                        {flexRender(cell.column.columnDef.cell, cell.getContext()) ??
                          String(cell.getValue() ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Q-table density">
          <ReactECharts
            option={{
              xAxis: {
                type: "category",
                data: rows.map((row) => row.agentName),
                axisLabel: { rotate: 20 },
              },
              yAxis: { type: "value" },
              color: ["#12343b", "#d28b36"],
              legend: { data: ["Entries", "Non-zero"] },
              series: [
                { name: "Entries", type: "bar", data: rows.map((row) => row.entryCount) },
                { name: "Non-zero", type: "bar", data: rows.map((row) => row.nonZeroCount) },
              ],
              tooltip: { trigger: "axis" },
            }}
            style={{ height: 300 }}
          />
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel
          title="Operation drill-down"
          actions={
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter operations..."
              className="rounded-full border border-line bg-paper px-3 py-2 text-sm outline-none"
            />
          }
        >
          <div className="max-h-[400px] space-y-3 overflow-auto pr-1">
            {filteredOperations.slice(0, 50).map(([operationId, payload]) => (
              <div key={operationId} className="rounded-2xl bg-paper p-4">
                <div className="font-mono text-xs text-slate">{operationId}</div>
                <pre className="mt-2 overflow-auto text-xs text-ink">
                  {JSON.stringify(payload, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Cached bootstrap tables">
          <div className="space-y-4 text-sm">
            <div className="rounded-2xl bg-paper p-4">
              <div className="text-xs uppercase tracking-wide text-slate">
                Cached Value Agent entries
              </div>
              <div className="mt-2 font-display text-2xl font-semibold text-ink">
                {formatNumber(Object.keys(cachedQtables?.valueAgent ?? {}).length)}
              </div>
            </div>
            <div className="rounded-2xl bg-paper p-4">
              <div className="text-xs uppercase tracking-wide text-slate">
                Cached Header Agent entries
              </div>
              <div className="mt-2 font-display text-2xl font-semibold text-ink">
                {formatNumber(Object.keys(cachedQtables?.headerAgent ?? {}).length)}
              </div>
            </div>
            <p className="rounded-2xl border border-dashed border-line bg-paper p-4 text-slate">
              Cached q-tables are bootstrap-only. Runtime q_tables.json remains the
              primary source for session analysis.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
