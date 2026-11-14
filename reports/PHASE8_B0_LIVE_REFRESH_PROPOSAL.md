# Phase 8 — live librarian-v2 refresh proposal (not executed)

2026-11-14. Owner requested a sized proposal and approval before mutation. **No live catalog/store update has been performed.** Current navigation remains the G: S0 copy.

## Current state and measured sizes

Read-only live catalog inspection still resolves librarian-v2 to graph `g_1bbebca16afc45c39b2f2f8a`, snapshot `snapshot:f2bce47cb554c2304bd1e148d8cc1f6e5aa8363c5588cd3bc9912a90351695bc` (424 entities), with **30,691,328-byte** code store under F:/uv-data/Geo_Grapher/output/named-graphs/graphs/.

The S0 copy's native code store, retaining the old snapshot plus the pinned-master refresh, is **515,829,760 bytes**. Its complete four-graph QA workspace is **1,365,212,153 bytes**; copying all four graphs is unnecessary for this proposal. The small catalog is **106,496 bytes**. The S0 refresh used 146 supported src files / 3,035,864 bytes, with 29,380 entities, but retained generated app.js and did not select root ui/src TypeScript. Those exact counts are not promised for the A4-filtered refresh.

Disk at proposal time: G **133,738,700,800 bytes free**; F **3,417,079,808 bytes free**. The latter is below the agreed 5 GiB floor. No F: copy or index build is proposed. Conservatively, do not publish even the small catalog update until F has at least 5 GiB free; reaching that floor requires about **1.82 GiB** additional space, preferably **2 GiB** headroom. No cleanup is authorised or attempted here.

## Proposed bounded operation, subject to approval

1. Finish/test A4 hygiene first: exclude generated native UI JS bundles and analogous build products, select actual ui/src TypeScript source. Pin the then-approved source revision and record selection/exclusion evidence. Never ingest the source credential paths.
2. Create a fresh G:/Libraries/_qa/phase8-b0-live-refresh-<run>/ destination. Back up the original native code store via SQLite backup, preserving its immutable old snapshot; build/validate the new snapshot there. Keep the live catalog untouched throughout build and validation. Preserve first build/failure evidence. No other graph stores need copying.
3. Allocate **4 GiB maximum additional G: space** for the copied code store, refreshed index, temporary data, catalog backup and validation artifacts. This is a conservative budget over the measured ~492 MiB S0 store; re-check estimates/free space immediately before building and stop if selection or actual growth exceeds the bound. G remains well above 5 GiB. No paid model/extraction work.
4. After validation, re-check the live graph head has not changed. With publication coordinated against the running hub, update only the librarian-v2 catalog binding in the existing F: catalog to the validated G: store/new snapshot through the catalog's supported publication path. Keep graph identity, old snapshot in the copied store, original F: code store and a G: catalog backup. Do not overwrite another session's newer head. The publication transaction is small; allow **1 MiB** catalog/WAL headroom separately from the G: build allowance. No actual publication command has been run or a new live-write script installed.
5. Verify live hub discovery and a source-backed staging/closure query expose the new head; record exact counts/revision/filters, old-snapshot readability, catalog diff and source failures. If the live process caches catalog state, coordinate a reload/restart rather than claiming visibility from disk alone. Do not alter any agent binding or merge a branch to accomplish the refresh.

The proposed live binding would depend on that G: directory: mark it persistent/live-backed, excluded from disposable QA cleanup. A later move to a dedicated permanent store location needs its own path/space check, never silent deletion of the old store.

**Requested approval:** one new-snapshot live native-graph refresh under this 4 GiB G: / 1 MiB F: publication allowance, retaining all old data, after the A4 change is tested and F: satisfies the reserve. Approval is not inferred from the S1 authorisation. If the owner prefers a different persistent G: location, select it before execution. Until then, use only the existing G: navigation copy.
