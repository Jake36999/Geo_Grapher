# Phase 8 B0 — S5 catalogue navigation candidate

2026-11-15 (owner/client date). Native `941d1a5`; Geo product `990713c`.
No merge, push, model binding change or paid call. S6/S6b and R remain ahead;
this is a stage record, not the owner acceptance stop.

Source catalogue views now expose recorded relevance, a rollup of `log_use` events
and Application notes, and generated deep-read chapter summaries. Unexamined chapters
remain explicit. The person sees all chapters, initially collapsed; the model catalogue
projection shows eight and reports truncation so graph location remains the read route.
Chapter summary excerpts are labelled; source text is rendered inertly.

The original link downloads the exact named attachment through an authenticated,
loopback, attachment-only HTTP route. It never serves conversions or credential paths,
never extracts/indexes merely to resolve the download, and streams rather than loading
the whole original into server memory. Missing originals stay unavailable/catalogue-only.
The ordinary Source note is retained; no conversion is offered as a person's source.

Native source search carries recorded use across source intents, beyond precedent.
One search reads each session history once for all its hits; the next search re-reads
it and sees new events. Application metadata is copied from the existing index where
available, not opened once per hit. These counts are recorded activity, not evidence
of efficacy. Generated Application records retain their existing taint classification.

Native paper artifacts carry an export-time catalogue history snapshot. Geo persists
it with import provenance and returns a bounded use-rollup field on paper cards.
Histories from different original documents stay separate, without summing duplicate
source histories. Legacy cards say `not_recorded`, not zero uses. Responses explicitly
say **at graph import; not live session history**. New uses require a fresh projection/
import for the graph view; native reads remain current. Imported catalogue metadata is
bounded at 8,192 serialized characters; emitted rollups at 2,400, retaining counts and
reporting detail cuts. No live paper graph or catalog binding was refreshed here.

Evidence under `G:/Libraries/_qa/phase8-b0-20261114/evidence/`; all first results retained:

| Check | Retained outcomes |
|---|---|
| Native catalogue RED | `s5-catalogue-navigation-red.txt`: 4 failed; initial focused implementation: 26 passed |
| Search repeated I/O RED | `s5-catalogue-io-red.txt`: 2 failed / 3 passed; one also exposed a test relying on another module to register tools; fixed isolated setup. Follow-up with search contracts: 33 passed |
| Person HTTP RED | `s5-catalogue-person-red.txt`: 1 failed / 6 passed |
| HTTP first implementation | first green-named log: 2 failed / 22 passed; index lookup triggered extraction; second: 1 failed / 23 passed (missing os import); third: 24 passed. Names do not turn failed runs into passes |
| Missing-original lookup RED | 1 failed / 6 passed; metadata-only resolution fixed, then 7 passed |
| All person chapters RED | 1 failed / 7 passed; person projection expanded, model projection stays bounded |
| **Final native selection** | `s5-catalogue-final-targeted.txt`: **68 passed**, 14.64 s; catalogue, search/contracts, durable results, index worker and paper projection |
| Browser component RED | missing new module, retained as `s5-catalogue-ui-red.txt` |
| Browser component final | **7 checks passed**, zero model calls, including default collapse, expand, original request, unread status and inert hostile HTML text; screenshot `s5-catalogue-ui-final/catalogue.png` |
| Native UI | TypeScript and packaged UI build passed; generated bundle rebuilt on the feature branch |
| Geo rollup RED | 3 failed / 6 passed; implementation: 72 passed with paper regressions |
| Geo single-card cap RED | 1 failed / 9 passed; final paper selection **73 passed**, 4.43 s |

The native declaration guard still has **185 declarations / zero problems** after
reviewing get_note's changed output. Authorship coverage remains native A **92/92**,
B **13/13**, C **80 n/a**; Geo A **37/37**, B **3/3**; external adapter **1/1**.
These counts do not certify the pending S6 attached-root/index paths. Full suites in
the S4 report remain their original rows; S5 counts above are targeted, not new full
suite counts. The final S6 fixture and full suites will cover the integrated candidate.

Reproduction: use the native D: Python from neutral `F:/uv-data`, `PYTHONPATH` set to
the G: feature `src`, TEMP/TMP and fresh `--basetemp` on G:. Geo uses its pinned F:
wheel environment with both feature `src` and repository root on PYTHONPATH.

```powershell
& D:/Librarian_V2/.venv/Scripts/python.exe -m pytest G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_phase8_catalogue_navigation.py -q --basetemp <fresh-G-directory>
# From the native ui directory, using a fresh explicit output directory:
$env:LIBRARIAN_PHASE8_QA = '<fresh-G-directory>'
node phase8-catalogue-smoke.mjs
```

Spend **$0**. Continue to S6/S6b and the native intake retrofit R. Owner-created
attachments still need complete indexing, third-party attachments catalogue-only;
model-card precedence and reviewed route-expectation drafts are not yet delivered.
Combined Wave L+B0 merges still require separate owner approvals at STOP S6.
