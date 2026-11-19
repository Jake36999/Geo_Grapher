# How a folder is read when it is added

This is the policy behind **Add folder** (the Build tab in the right panel) and `geographer.workspace_init.scan`.
The code is the source of truth for the signals; this page records what they are for and the owner decisions that
shape them.

## What the scan does

`scan(root)` walks a folder once and proposes **partitions**: parts that are ingested as separate graphs. It goes
only as deep as the folder is split into separate graphs, and no deeper. Every partition is a *suggestion*
(`suggestion.accepted` is `False`); a person ticks what to bring in. Nothing is ingested by the scan itself.

Each partition has a **role**, from the folder's name, content and structure:

| Role | Signal |
|---|---|
| `current` | the default: the folder's own files (`residual` holds everything outside the other partitions) |
| `legacy` | folder named `legacy`, `archive`, `old`, `deprecated`, `attic` |
| `docs` | folder named `docs`, `doc`, `notes`, `wiki` |
| `transcripts` | folder named `transcripts`, `chats`, `logs` |
| `third_party` | folder named `third_party`, `vendor`, `external…`, `repos`, `refs`, `*-master`, `*-main`; or a nested Git repository; or a licence file present |
| `external_reference` | in the name map for `vendor`, `third_party`, `external`, `refs`, but each of those names also matches a third-party signal above, so today the scan reports `third_party` for them |
| `research_docs` | PDF-dominant folder |
| `data` | bulk data files (`.csv`, `.pcap`, `.parquet`, `.h5`, `.npy`) |

Caches, builds, backups, binaries, empty folders, symlinks and credential files are excluded and never partitioned.

## Unlicensed sources (owner decision, 2026-11-19)

An **unlicensed source can be ingested, copied and graphed like any other.** It must only never appear in the end
product when that product is published as our own work. Referencing (citing the source) is already how that is
handled.

So the scan **labels** and never **gates**:

- `suggestion.publication` is `reference` for `third_party`, `external_reference` and `research_docs` (someone else's
  work, cited and not published as our own), and `own` otherwise.
- `suggestion.licence` is `found` or `none_found` for `third_party` and `external_reference`, and `not_applicable`
  otherwise. `suggestion.licence_files` counts licence files anywhere in the partition (`LICENSE*`, `LICENCE*`,
  `COPYING*`), so a folder of repositories is `found` if any has one.
- A `none_found` partition gets the reason "no licence file found; ingested and copied as usual, cited and not
  published as our own work".
- These labels do **not** change `accepted`, the trust tier, the modality, or what `apply()` ingests. An unlicensed
  partition starts ticked in the review sheet like every other.

The folder map shows the labels as tags ("cited, not published as our own", "no licence file"). The labels are for the
person (and for any later publish step) to read; nothing in the scan withholds a source.

## Correcting a role

The scan guesses a role for every part, and a guess can be wrong (a folder named `vendor` that is really your own
code). In the review sheet the role tag of each part is a selector, so a person can correct it instead of only
unticking the part.

- A correction changes how the part is **labelled and filed**, not how it is read. The part is ingested the same way
  and by the same files; only its federation stratum (role, trust tier, modality) and its publication label follow the
  chosen role.
- The labels a role implies come from one place, `workspace_init.role_policy()`. The plan carries it as
  `role_policy`, and the sheet reads it, so the scan and the sheet cannot disagree about what "own" or "third-party"
  means. Choosing a role that looks for a licence file (`third_party`, `external_reference`) looks again at the files
  already counted for that part.
- Only corrections that differ from the suggestion, for parts that will be ingested, are sent as `role_overrides`
  (part key to role). The server refuses an unknown part or an unknown role before anything is ingested.
- The sheet states plainly that a role was chosen by a person ("you chose “own”; the scan suggested
  “third-party”"), and the text map shows the corrected role.

## Not decided here

- Anything that enforces "not published as our own work" at publish time; that belongs to the publishing step.
