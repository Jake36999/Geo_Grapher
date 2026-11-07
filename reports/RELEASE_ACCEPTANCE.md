# Remaining release acceptance

Use the approved criteria, not the presence of controls, as acceptance. These checks remain open:

1. On Windows 11 / i5-1235U / 16 GiB / Iris Xe at 1440×900/DPR1, record browser, adapter, build hashes, backend preparation and cold/warm state. Use `geographer-benchmark-v1` with 50k/150k facts, scene budgets 500/2000 and actual displayed/total counts.
2. Record overview, orbit/pan, selection feedback, cached focus/filter, first witnesses and final-build 10-minute heap/GPU distributions. Compare with product §15. Annotate concurrent workload/instrumentation; do not substitute development-host results.
3. With a recorded screen-reader/version, complete explore/enter/back, connection evidence and incoming impact via hierarchy/list/matrix. Review focus order/visibility, tab arrows, drawers, reflow and reduced motion. Automated scans alone do not close C11/C12.
4. Compare spatial, flat search and conventional table/matrix on the tasks below. Randomise order; use identical snapshots/questions/evidence. Score correctness against pinned source/fixture oracles, time, evidence recovery and ability to state current container/scope. Preserve failed outcomes.

| Task | Required evidence |
|---|---|
| Locate implementation | Qualified identity, snapshot/path/lines. |
| Explain cross-subsystem link | Ordered endpoints, type/status and witnesses. |
| Distinguish callers/callees | Correct direction and original source occurrence. |
| Investigate impact | Original directed witness path with uncertainty/scope. |
| Find quotient cycle | Grouping/filter, SCC members, leaf witnesses; do not infer a leaf cycle solely from aggregation. |
| Identify rule violation | Versioned model/rationale and violating witness; incomplete evidence makes absence inconclusive. |

For LLM comparisons, use equal token budgets and identical questions/oracles. Compare correctness and citations, not payload size. Retain full-envelope counts, omissions/cursors and endpoint closure. A plausible answer without its required witness is not an evidence-backed success.

Do not mark all release gates passed until recorded outcomes meet the approved criteria. The local engineering build does not imply external publication or deployment.

## P5.5 evidence update — 6 November 2026

The [P5.5 report](P5_5_GATE_REPORT.md) records five-arm offline retrieval comparisons and a small actual isolated subagent pilot. Larger model tests are shelved at the user's request for their own DeepInfra-connected harness; four oracle-free prompts and an actual-result importer are prepared under `output/phase5/p55-deepinfra-handoff/` and `evaluation/handoff.py`.

The pilot found a missing original-document citation in the graph-backed stale-document answer, despite correct immediate-callee reasoning. That failure remains open. The unchanged development-host workload also recorded 6.22-second cold preparation under concurrent load; this does not meet or close target-device C14. The post-pilot rubric correction and small sample cannot establish a comparative accuracy result. Human/AT, whole-provider-token model trials, cold preparation and final-build soak remain separate acceptance items.

7 November follow-up: [MCP grounding remediation](MCP_GROUNDING_REMEDIATION.md) fixes the deterministic document selection/presentation gap and adds task-local validation plus bounded opt-in repair. A new four-request handoff is prepared for the user's harness. Original failed model outcomes remain unchanged; improved paid-model performance and all external acceptance gates remain unverified.
