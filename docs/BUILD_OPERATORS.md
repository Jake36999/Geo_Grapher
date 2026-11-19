# Build operators

The **Build** tab of the right panel is where a person makes something new from graphs they already have. Every
result is either a new graph or a declared link. **A source graph is never changed.** This page records what each
operator does and the rules that hold for all of them.

| Operator | Idea | Result |
|---|---|---|
| Add a folder | read a folder, choose which parts become graphs | new graphs (see [the ingestion policy](INGESTION_POLICY.md)) |
| Keep only / Remove | cut a graph down to a selection, or without it | a new derived graph |
| Combine graphs | put several graphs in one | a new merged graph |
| Compare graphs | what two graphs share and what only one has | nothing: a read-only answer |
| Link graphs | say how two graphs relate | a declared link, which can be taken back |

## Keep only or remove

Select files or folders on the canvas and press the scissors ("Keep only or remove selection…"). The Build tab opens
with the selection, and the choice is made there:

- **Keep only these**: a new graph of just the selected paths.
- **Remove these**: a new graph of everything except them.

Before anything is made, the tab shows what the choice would do, counted from the source graph: files and items
kept or removed, and how many relationships cross the cut and would be dropped. A choice that would keep or remove
nothing cannot be made. The counts are the source graph's own; the new graph is read again from the folder, so its
totals can differ slightly (the answer says so).

- The new graph is a **derived** graph (`graph_kind: derived`). Its profile records how it was made
  (`derived_how`: the mode and the paths) and which graph it came from.
- Its id is deterministic and the two modes are separate: doing the same thing again refreshes the graph, it never
  duplicates it, and "keep only X" and "remove X" are different graphs.
- A graph that already limits what it includes cannot be cut down with "keep only" (the two limits cannot be
  combined); removing paths from it still works.

API: `POST /api/graphs/{graph_id}/derive-preview` and `POST /api/graphs/{graph_id}/prune`, each taking either
`exclude_rel_paths` or `keep_rel_paths` (never both).

## Compare graphs

Pick two of the checked graphs. The answer is counts first, then a bounded sample behind each:

- **Identical**, **same contract rewritten**, **same place in the graph**, **same name changed**: how functions,
  methods and classes in one graph match those in the other (the fingerprint classes of `cross_graph.diff_rows`).
- **Only in** each graph.
- Dependency loops that appeared, dissolved, or changed.

It compares functions, methods and classes, and says so. It writes nothing. Graphs ingested before fingerprints
existed cannot be compared, and the panel says that rather than showing an empty result.

API: `POST /api/graphs/compare` with `graph_a` and `graph_b`.

## Link graphs

A declared link is how a person says two graphs relate. It is stored as a **bridge**: kept apart from extracted
facts, bound to the snapshots it was declared against (so a later re-read can mark it out of date), and never an edit
to either graph.

- Each end is the **whole graph** (`root`), the **item selected on the canvas** (`entity:<id>`), or a reference typed
  in (`doc:12`, `concept:7`). The server resolves both ends and refuses one that does not exist.
- The kinds are `reference`, `concept equivalence` and `document identity`. A reason is required.
- Declaring a link is the owner's own action, so it counts as the owner decision a link across a third-party
  boundary needs. Such a link can only be a `reference`.
- A link can be **taken back**: only the link goes (and the lineage it kept); both graphs and every extracted fact
  stay as they were.
- The draft is kept by the workspace, not by the canvas view, because choosing the second item can switch the active
  graph.

API: `POST /api/graphs/links`, `DELETE /api/graphs/links/{bridge_id}`, and the existing `POST /api/graphs/bridges`
to list.

## Graph colours

Each graph has an accent colour so graphs can be told apart when several are shown. It marks the graph's own
enclosure and appears as a dot beside its name; what is inside keeps the colour of its content. The colours are a
reserved set kept apart from the content hues and the relationship colours. They are assigned from the graph's id
(so a graph keeps its colour), a person can choose another in the Graphs tab, and the choice is remembered for the
browser. With more graphs than colours, colours repeat.
