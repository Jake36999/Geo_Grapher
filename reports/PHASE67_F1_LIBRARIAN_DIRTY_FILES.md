# F1 / W2-7: untouched Librarian master inventory

Read-only snapshot, 2026-11-14. Checkout **D:/Librarian_V2**, branch **master**, HEAD **c4eb76ff1c2b78346fd7743dadda5d6b170427b5**. `git status --short --untracked-files=all` reports **18 paths: 13 modified tracked files, 5 untracked files**. None is staged. No file below was staged, stashed, reverted, edited, moved or deleted in this F1 pass. No ownership attribution is inferred from filenames or commit history.

| Status | Exact path relative to D:/Librarian_V2 (links are absolute) |
|---|---|
| Modified | [reports/2026-11-05-ui-wave/STATUS.md](D:/Librarian_V2/reports/2026-11-05-ui-wave/STATUS.md) |
| Modified · F1 item 3 | [scripts/delegate_deepinfra.py](D:/Librarian_V2/scripts/delegate_deepinfra.py) |
| Modified | [src/resource_librarian/agent_runtime.py](D:/Librarian_V2/src/resource_librarian/agent_runtime.py) |
| Modified | [src/resource_librarian/loop.py](D:/Librarian_V2/src/resource_librarian/loop.py) |
| Modified | [src/resource_librarian/mcp_client.py](D:/Librarian_V2/src/resource_librarian/mcp_client.py) |
| Modified | [src/resource_librarian/standard/profiles/history.yaml](D:/Librarian_V2/src/resource_librarian/standard/profiles/history.yaml) |
| Modified | [src/resource_librarian/standard/profiles/software-systems.yaml](D:/Librarian_V2/src/resource_librarian/standard/profiles/software-systems.yaml) |
| Modified | [src/resource_librarian/starter/About/Recommended MCP Servers.md](<D:/Librarian_V2/src/resource_librarian/starter/About/Recommended MCP Servers.md>) |
| Modified | [src/resource_librarian/ui/app.js](D:/Librarian_V2/src/resource_librarian/ui/app.js) |
| Modified | [tests/test_capabilities.py](D:/Librarian_V2/tests/test_capabilities.py) |
| Modified | [tests/test_loop.py](D:/Librarian_V2/tests/test_loop.py) |
| Modified | [tests/test_profiles.py](D:/Librarian_V2/tests/test_profiles.py) |
| Modified | [ui/src/settings.ts](D:/Librarian_V2/ui/src/settings.ts) |
| Untracked | [Theorising_transcription.md](D:/Librarian_V2/Theorising_transcription.md) |
| Untracked | [reports/2026-11-05-ui-wave/HOST-QUALIFICATION.md](D:/Librarian_V2/reports/2026-11-05-ui-wave/HOST-QUALIFICATION.md) |
| Untracked | [reports/2026-11-05-ui-wave/native-sandbox-policy.png](D:/Librarian_V2/reports/2026-11-05-ui-wave/native-sandbox-policy.png) |
| Untracked | [tests/test_external_bundles.py](D:/Librarian_V2/tests/test_external_bundles.py) |
| Untracked | [tests/test_mcp_structured_bounds.py](D:/Librarian_V2/tests/test_mcp_structured_bounds.py) |

W2-7 specifically notes that `mcp_client.py` and `test_mcp_structured_bounds.py` predate the wave-2 session, alongside dirty Codex UI-wave work. That history does not establish current hunk ownership for the other paths. The owner must coordinate disposition, including any mixed ownership within a file; do not bundle this inventory into one integration commit.

The inspected delegation diff adds only opt-in reasoning/thinking controls. Its disposition is separately requested in F1 item 3; an approval for that change must not be taken as ownership of the other 17 paths.

Re-inspect this inventory before integration because owners may change files after this snapshot. Clearing the working tree is an owner action, not something implied by approval of a later feature merge. Feature branches awaiting review: **geo-grapher-survey 70ffe38**, **geo-grapher-wave4 737ea28**.
