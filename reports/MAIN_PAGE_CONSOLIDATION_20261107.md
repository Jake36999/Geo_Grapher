# Main-page consolidation — 7 November 2026

**Superseded:** the user clarified that moving the separate viewer to the main
port was not the intended design. The original workspace has now been restored,
with graph modes integrated into it. See
[the corrected implementation](INTEGRATED_MAIN_WORKSPACE_20261107.md).

The shared graph viewer is now served directly at **http://127.0.0.1:8765/**.
Root HTML selects the graph workspace without redirecting to `/collection/`.
The collection path is a compatibility alias to root. The separate 8774 viewer
has been stopped; its optional compatibility listener is not running.

The original ToolSet database was preserved. Its UI remains accessible from the
main page at `/legacy/`, and original `/api/v1`, `/api/v1.1`, `/mcp` and v1.1 MCP
routes retain their existing single-store behavior. Scoped graph HTTP routes are
available on the same origin; graph MCP is `/graph-hub/mcp`. Graph ownership and
query isolation are unchanged. No repository was re-ingested or merged.

The maintained startup command is:

```powershell
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher'
./output/wheel-env/Scripts/python.exe -m geographer serve --database output/toolset.sqlite --catalog output/named-graphs/catalog.sqlite --transport http --port 8765
```

Verification: 29 targeted backend tests passed, including direct root rendering,
collection redirects, original and scoped APIs, and initialization of both MCP
endpoints. The production build passed. Live browser checks passed at root with
one canvas and no automatic detail tiles, then opened the preserved original UI.
Independent graph navigation/search smoke checks also passed on port 8765.
Evidence: `output/main-workspace/browser.json`, `output/main-workspace/main.png`.

The shared-workspace Playwright regression suite is run through
`playwright.graphs.config.cjs`; its results are recorded in
`output/spatial-controls/browser-results.json`. README, CLI help/defaults and
local operations guidance now point users to the main origin.
