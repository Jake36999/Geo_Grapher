import type { ReactNode } from "react";
import type {
  Filter,
  ViewportFrameData,
} from "../../contracts/geographer.wire";
import type { GroupMode } from "./api";
export interface WorkspaceGraph {
  graph_id: string;
  label: string;
  snapshot_id: string;
  availability?: string;
  error?: string;
  repo_ids?: string[];
  /** Reviewed member folder of each repository id (absolute paths). */
  repo_roots?: Record<string, string>;
  owned_store?: boolean;
  bridge_count?: number;
  graph_kind?: string;
  copied_from?: string | null;
}
export interface WorkspaceSettings {
  view: "spatial" | "list" | "matrix";
  theme: "dark" | "light";
  beta: number;
  lens: boolean;
  contextRadius: 0 | 1 | 2;
  grouping: GroupMode;
  filter: Filter;
  panelSizes: [number, number];
}
export interface GraphPick {
  serial: string;
  graph_id: string;
  snapshot_id: string;
  local_id: string;
  edge: boolean;
  enter: boolean;
  frame: ViewportFrameData;
  camera?: { eye: [number, number, number]; target: [number, number, number] };
}
export interface WorkspaceControls {
  active: string;
  graphs: WorkspaceGraph[];
  selected: string[];
  tools: ReactNode;
  /** The right panel's Build tab: add a folder, combine, link. */
  build?: ReactNode;
  settings?: WorkspaceSettings;
  showBridges: boolean;
  restoreGraphs: (ids: string[]) => void;
  reloadGraphs: () => Promise<unknown>;
  pending?: GraphPick;
  consume: () => void;
  pick: (pick: Omit<GraphPick, "serial">) => void;
  settingsChanged: (settings: WorkspaceSettings) => void;
  focus: Record<string, { snapshot: string; id: string }>;
  remember: (graph: string, snapshot: string, id: string) => void;
}
