import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import popper from "cytoscape-popper";

let registered = false;

export function registerCytoscapePlugins() {
  if (registered) {
    return;
  }
  cytoscape.use(fcose);
  cytoscape.use(popper as never);
  registered = true;
}
