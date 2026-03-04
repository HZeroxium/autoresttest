import { PropsWithChildren, ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { DatasetSummary, RunManifestSummary } from "@/lib/schemas/api";

type AppLayoutProps = PropsWithChildren<{
  datasets: DatasetSummary[];
  runs?: RunManifestSummary[];
  selectedDatasetId?: string;
  selectedRunId?: string;
  title: string;
  subtitle?: string;
  headerContent?: ReactNode;
}>;

export function AppLayout(props: AppLayoutProps) {
  return <AppShell {...props} />;
}
