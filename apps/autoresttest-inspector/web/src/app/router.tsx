import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";

import { DatasetRoutePage } from "@/routes/datasets.$datasetId";
import { RunRoutePage } from "@/routes/datasets.$datasetId.runs.$runId";
import { IndexRoutePage } from "@/routes/index";

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: IndexRoutePage,
});

const datasetRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/datasets/$datasetId",
  component: () => {
    const { datasetId } = datasetRoute.useParams();
    return <DatasetRoutePage datasetId={datasetId} />;
  },
});

const runRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/datasets/$datasetId/runs/$runId",
  component: () => {
    const { datasetId, runId } = runRoute.useParams();
    return <RunRoutePage datasetId={datasetId} runId={runId} />;
  },
});

const routeTree = rootRoute.addChildren([indexRoute, datasetRoute, runRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
