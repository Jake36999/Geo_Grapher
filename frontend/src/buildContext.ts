import { createContext, useContext } from "react";

/** Something a declared link can point at, in the graph the person is looking at. */
export interface Endpoint {
  graph_id: string;
  /** A bridge endpoint: `entity:<id>`, `doc:<n>`, `concept:<n>` or `root`. */
  ref: string;
  label: string;
}

/** Files or folders selected on the canvas, waiting for the person to say what to make of them. */
export interface DeriveRequest {
  graph: string;
  paths: string[];
  /** Why there is nothing to act on, when the selection held no files of this graph. */
  message?: string;
}

/**
 * What the canvas tells the Build tab. The tab's panels are built where the workspace lives (above the
 * canvas, which remounts whenever another graph becomes the active one) and rendered inside the canvas
 * view, so what only the canvas knows reaches them through here.
 */
export interface BuildContextValue {
  /** The item selected in the active graph, when it is something a link can point at. */
  selection?: Endpoint;
  derive?: DeriveRequest;
  /** The file or folder selected in the active graph, when it can start a keep-only or remove. */
  selectedPath?: { graph: string; path: string; label: string };
  /** Begin a keep-only or remove from paths a person chose without the canvas box tool. */
  startDerive: (graph: string, paths: string[]) => void;
  clearDerive: () => void;
  /** A graph was made from a selection: the graph list needs to be read again. */
  derived: () => void;
  /** Go to one end of a declared link; a message says why it cannot (AR-F08). */
  jumpTo?: (graphId: string, ref: string) => string | undefined;
}

export const BuildContext = createContext<BuildContextValue>({
  startDerive: () => {},
  clearDerive: () => {},
  derived: () => {},
});
export const useBuild = () => useContext(BuildContext);
