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
  settings?: WorkspaceSettings;
  showBridges: boolean;
  restoreGraphs: (ids: string[]) => void;
  pending?: GraphPick;
  consume: () => void;
  pick: (pick: Omit<GraphPick, "serial">) => void;
  settingsChanged: (settings: WorkspaceSettings) => void;
  focus: Record<string, { snapshot: string; id: string }>;
  remember: (graph: string, snapshot: string, id: string) => void;
}
