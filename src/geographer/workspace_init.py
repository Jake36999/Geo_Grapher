"""Initialize a workspace into disjoint partitions."""
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from geographer import source
from geographer.model import digest
from .credentials import credential_path, refuse_credentials
from . import folder_inventory

# Source files that make a folder code (2026-11-17: C, Rust and Go repositories counted as
# "no code", so 16 code repositories were planned into a docs graph).
CODE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".ipynb", ".c", ".h", ".cc", ".cpp", ".hpp",
                 ".cxx", ".rs", ".go", ".java", ".kt", ".rb", ".cs", ".swift", ".php", ".scala",
                 ".lua", ".sh", ".ps1")


PLAN_VERSION = "workspace-init-v1"
HYGIENE_DIRS = source.EXCLUDED | {
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", "dist", "build",
    "target", ".idea", ".vscode", "wheel-env", "site-packages", "output", "tmp",
    "test-results", "librarian-app", "ghostunnel_static_build"
}


def scan(root, catalog=None, *, inventory=None) -> dict:
    """Scan a directory and return a plan."""
    root = Path(root).resolve()
    refuse_credentials(root)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    inventory = folder_inventory.validate(root, inventory) if inventory is not None else folder_inventory.collect(root, HYGIENE_DIRS)
    metadata = {r[0]: r[1:] for r in inventory['entries']}
    excluded = [{'rel': name.rstrip('/'), 'reason': 'survey_exclusion' if size == -2 else 'symlink'}
                for name, size, _ in inventory['entries'] if size in (-1, -2)]
    credential_refusals = list(inventory.get('credential_refusals', {}).get('paths', []))
    unsupported_by_suffix = {}
    manual_steps = []
    partitions = {}
    
    # Track which directories start partitions
    partition_roots = {}
    
    # Role mapping
    role_map = {
        "legacy": {"legacy", "archive", "old", "deprecated", "attic"},
        "external_reference": {"vendor", "third_party", "external", "refs"},
        "transcripts": {"transcripts", "chats", "logs"},
        "docs": {"docs", "doc", "notes", "wiki"},
    }

    # First pass: identify partitions
    for dirpath, dirnames, filenames in folder_inventory.walk(root, inventory):
        dir_path = Path(dirpath)
        dir_rel = dir_path.relative_to(root).as_posix()
        if dir_rel == ".":
            dir_rel = ""
        if dir_rel and not dirnames and not filenames and metadata.get(dir_rel + '/', [0])[0] == 0:
            excluded.append({'rel': dir_rel, 'reason': 'empty folder'})
            continue

        # Check for exclusions
        excluded_reason = None
        dirname = dir_path.name
        if dirname in HYGIENE_DIRS:
            excluded_reason = "hygiene"
        elif dirname.endswith(".egg-info"):
            excluded_reason = "hygiene"
        elif dirname.lower().endswith("cache"):
            excluded_reason = "hygiene"
        elif os.path.islink(dirpath):
            excluded_reason = "symlink"
        else:
            try:
                st = os.lstat(dirpath)
                if getattr(st, "st_file_attributes", 0) & 0x400:
                    excluded_reason = "reparse_point"
            except (AttributeError, OSError):
                pass

        if excluded_reason:
            excluded.append({"rel": dir_rel, "reason": excluded_reason})
            dirnames[:] = []
            continue

        # Determine role
        dir_name_lower = dir_path.name.lower()
        role = "current"
        for r, names in role_map.items():
            if dir_name_lower in names:
                role = r
                break
        reasons = []
        if (dir_name_lower.startswith(('third_party', 'vendor', 'external'))
                or dir_name_lower in {'repos', 'refs'} or dir_name_lower.endswith(('-master', '-main'))):
            role = 'third_party'; reasons.append('third-party folder-name signal')
        if dir_rel and (dir_rel + '/.git/' in metadata or dir_rel + '/.git' in metadata):
            role = 'third_party'; reasons.append('nested Git repository; ownership unconfirmed (remote credentials are not read)')
        if dir_rel and any(name.lower().startswith(('license', 'licence', 'copying')) for name in filenames):
            reasons.append('licence file; review upstream ownership')
            if role == 'current': role = 'third_party'
        suffixes = [Path(name).suffix.lower() for name in filenames if not credential_path(name)]
        if dir_rel and suffixes and role == 'current':
            if suffixes.count('.pdf') > len(suffixes) / 2:
                role = 'research_docs'; reasons.append('PDF-dominant folder')
            elif sum(s in {'.csv', '.pcap', '.pcapng', '.parquet', '.h5', '.npy'} for s in suffixes) > len(suffixes) / 2:
                role = 'data'; reasons.append('bulk data files')

        # Check if this directory should start a partition
        ancestors = []
        if dir_rel:
            parts = dir_rel.split("/")
            ancestors = ["/".join(parts[:i+1]) for i in range(len(parts)-1)]

        # Find if any ancestor already started a partition
        parent_partition_started = False
        for anc in ancestors:
            if anc in partition_roots:
                parent_partition_started = True
                break

        partition_key = None
        if role != "current" and not parent_partition_started:
            # This directory starts its own partition
            partition_key = dir_rel.replace("/", "__") if dir_rel else ""
            partition_roots[dir_rel] = {
                "key": partition_key,
                "subtrees": [dir_rel],
                "role": role,
                "suggestion_reasons": reasons or [f'folder-name signal: {role}'],
                "file_counts": {},
                "bytes": 0,
                "exclude_globs": [],
            }
        elif parent_partition_started:
            # Find which ancestor started the partition
            for anc in reversed(ancestors):
                if anc in partition_roots:
                    partition_key = partition_roots[anc]["key"]
                    break

        # Process files in this directory
        for fname in filenames:
            fpath = dir_path / fname
            if credential_path(fpath.relative_to(root)):
                credential_refusals.append(fpath.relative_to(root).as_posix())
                continue
            suffix = fpath.suffix.lower()
            if suffix in {'.blend', '.blend1', '.blend2', '.log', '.bak', '.exe', '.dll', '.so', '.bin'}:
                excluded.append({'rel': fpath.relative_to(root).as_posix(), 'reason': 'binary, backup or log'})
                continue
            
            # Count unsupported files
            if suffix not in source.SUPPORTED and suffix not in {".pdf", ".tex", ".bib"}:
                suffix_key = suffix if suffix else ""
                unsupported_by_suffix[suffix_key] = unsupported_by_suffix.get(suffix_key, 0) + 1
            
            # Manual steps for PDFs
            if suffix == ".pdf":
                parent_rel = dir_rel
                existing = next((s for s in manual_steps if s["dir"] == parent_rel), None)
                if existing:
                    existing["pdf_count"] += 1
                else:
                    abs_dir = str(fpath.parent)
                    manual_steps.append({
                        "kind": "paper_corpus",
                        "dir": parent_rel or ".",
                        "pdf_count": 1,
                        "command": f'python pipeline/run_pipeline.py --library "{abs_dir}" --dry-run'
                    })
            
            # Count files for partitions
            target_partition = None
            if partition_key:
                # We're in a named partition
                for part in partition_roots.values():
                    if part["key"] == partition_key:
                        target_partition = part
                        break
            elif not parent_partition_started:
                # We're in residual (but not under another partition)
                if "residual" not in partition_roots:
                    partition_roots["residual"] = {
                        "key": "residual",
                        "subtrees": [],
                        "role": "current",
                        "file_counts": {},
                        "bytes": 0,
                        "exclude_globs": [],
                    }
                target_partition = partition_roots["residual"]
            
            if target_partition:
                # Count supported and paper files
                if suffix:
                    target_partition["file_counts"][suffix] = target_partition["file_counts"].get(suffix, 0) + 1
                
                # Count bytes for supported files
                if suffix:
                    try:
                        target_partition["bytes"] += metadata[fpath.relative_to(root).as_posix()][0]
                    except OSError:
                        pass

        # Prune dirnames for excluded directories
        pruned_dirs = []
        for dname in list(dirnames):
            dpath = dir_path / dname
            drel = (Path(dir_rel) / dname).as_posix() if dir_rel else dname
            dname_lower = dname.lower()
            if metadata.get(drel + '/', [0])[0] == -2:
                dirnames.remove(dname)
                continue
            if credential_path(drel):
                credential_refusals.append(drel)
                dirnames.remove(dname)
                continue

            # Skip excluded dirs
            skip = False
            reason = "hygiene"
            if dname in HYGIENE_DIRS:
                skip = True
            elif dname.endswith(".egg-info"):
                skip = True
            elif dname_lower.endswith("cache"):
                skip = True
            elif os.path.islink(dpath):
                skip = True
                reason = "symlink"
            else:
                try:
                    st = os.lstat(dpath)
                    if getattr(st, "st_file_attributes", 0) & 0x400:
                        skip = True
                        reason = "reparse_point"
                except (AttributeError, OSError):
                    pass

            if skip:
                excluded.append({"rel": drel, "reason": reason})
                pruned_dirs.append(dname)
                dirnames.remove(dname)

    # Convert partition_roots to final partitions format
    partitions = {}
    for part in partition_roots.values():
        partitions[part["key"]] = part
    
    # Ensure residual exists
    if "residual" not in partitions:
        partitions["residual"] = {
            "key": "residual",
            "subtrees": [],
            "role": "current",
            "file_counts": {},
            "bytes": 0,
            "exclude_globs": [],
        }
    
    # Build exclude_globs for each partition
    # First, collect all excluded directories and other partitions
    all_exclusions = []
    for excl in excluded:
        all_exclusions.append(excl["rel"])
        all_exclusions.append(excl["rel"] + "/*")
    
    # Add other partition subtrees to residual exclusions
    for key, part in partitions.items():
        if key != "residual":
            subtree_root = part["subtrees"][0]
            all_exclusions.append(subtree_root)
            all_exclusions.append(subtree_root + "/*")
    
    # Sort all exclusions
    all_exclusions.sort()
    
    # Assign exclusions to partitions
    for key, part in partitions.items():
        if key == "residual":
            # Residual gets all exclusions
            part["exclude_globs"] = all_exclusions[:]
        else:
            # Other partitions get just their own subtree exclusions plus hygiene
            # Globs are relative to this partition's own root; it never excludes itself.
            prefix = part["subtrees"][0] + "/"
            part["exclude_globs"] = []
            for excl in excluded:
                if excl["rel"].startswith(prefix):
                    inner = excl["rel"][len(prefix):]
                    part["exclude_globs"].extend([inner, inner + "/*"])
            part["exclude_globs"].sort()

    # Sort file counts
    for part in partitions.values():
        part["file_counts"] = dict(sorted(part["file_counts"].items()))

    # Collect all file counts for archetype determination
    all_file_counts = {}
    for part in partitions.values():
        for suffix, count in part["file_counts"].items():
            all_file_counts[suffix] = all_file_counts.get(suffix, 0) + count

    # Archetype determination
    code_count = sum(all_file_counts.get(s, 0) for s in CODE_SUFFIXES)
    paper_count = sum(all_file_counts.get(s, 0) for s in (".pdf", ".tex", ".bib"))
    doc_count = sum(all_file_counts.get(s, 0) for s in (".md", ".txt"))
    total = code_count + paper_count + doc_count

    archetype = "notes_vault"
    if total > 0:
        if code_count / total >= 0.40:
            archetype = "software_engineering"
        elif paper_count / total >= 0.40:
            archetype = "academic_literature"
        elif code_count / total >= 0.10 and paper_count / total >= 0.10:
            archetype = "research_lab"

    # Stratum assignment
    default_modality = "code" if archetype in ("software_engineering", "research_lab") else "doc"
    default_trust_tier = "gold" if archetype in ("software_engineering", "research_lab") else "silver"

    stratum_rules = {
        "current": {"trust_tier": default_trust_tier, "modality": default_modality},
        "legacy": {"trust_tier": "bronze", "modality": default_modality},
        "external_reference": {"trust_tier": "silver", "modality": default_modality},
        "transcripts": {"trust_tier": "bronze_transcript", "modality": "transcript"},
        "docs": {"trust_tier": "silver", "modality": "doc"},
        "third_party": {"trust_tier": "bronze", "modality": default_modality},
        "research_docs": {"trust_tier": "bronze", "modality": "paper"},
        "data": {"trust_tier": "bronze", "modality": "doc"},
    }

    for part in partitions.values():
        role = part["role"]
        rules = stratum_rules.get(role, {})
        part["stratum"] = {
            "role": role,
            "trust_tier": rules.get("trust_tier", default_trust_tier),
            "modality": rules.get("modality", default_modality),
        }

        if role == 'third_party' and part['file_counts'].get('.pdf', 0) > sum(part['file_counts'].values()) / 2:
            part['stratum']['modality'] = 'paper'
        elif role == 'third_party' and not any(part['file_counts'].get(s, 0) for s in CODE_SUFFIXES):
            part['stratum']['modality'] = 'doc'
        purposes = {'current': 'own-current', 'legacy': 'own-legacy', 'docs': 'own-docs',
                    'third_party': 'third-party', 'research_docs': 'research-docs', 'data': 'data',
                    'transcripts': 'logs/transcripts', 'external_reference': 'third-party'}
        part['suggestion'] = dict(purpose=purposes[role], reasons=part.pop('suggestion_reasons', ['residual content; ownership requires review']), accepted=False)

    # Finalize partitions list
    partitions_list = sorted(partitions.values(), key=lambda x: x["key"])

    # Existing graph ID
    existing_graph_id = None
    if catalog:
        root_key_norm = os.path.normcase(str(root))
        for graph in catalog.graphs():
            if graph["root_key"] == root_key_norm:
                existing_graph_id = graph["graph_id"]
                break

    # Plan assembly
    plan_dict = {
        "plan_version": PLAN_VERSION,
        "root": str(root),
        "archetype": archetype,
        "partitions": partitions_list,
        "excluded": sorted({e['rel']:e for e in excluded}.values(), key=lambda x: x["rel"]),
        "unsupported_by_suffix": dict(sorted(unsupported_by_suffix.items())),
        "manual_steps": sorted(manual_steps, key=lambda x: x["dir"]),
        "existing_graph_id": existing_graph_id,
        "geographer_version": "0.2.0",
        "shared_survey_fingerprint": inventory['fingerprint'],
        "inventory_fingerprint": digest(inventory['entries']),
        "credential_refusals": {"count": len(credential_refusals), "paths": sorted(credential_refusals)},
    }

    # Add plan_id
    plan_dict["plan_id"] = digest({k: v for k, v in plan_dict.items() if k not in ("plan_id", "existing_graph_id")})

    return plan_dict


def apply(catalog, plan: dict, *, approved_keys: set[str], inventory=None) -> list[dict]:
    """Apply an approved plan to ingest partitions."""
    # Rescan and check staleness
    if inventory is not None:folder_inventory.check_current(Path(plan['root']).resolve(), inventory)
    new_plan = scan(plan["root"], inventory=inventory)
    if plan["plan_id"] != new_plan["plan_id"]:
        raise ValueError("PLAN_STALE: the folder changed since the plan was made; scan again")

    results = []
    root_path = Path(plan["root"])
    root_label = root_path.name

    for partition in plan["partitions"]:
        key = partition["key"]
        if key not in approved_keys:
            continue

        subtrees = partition["subtrees"]
        if key == "residual":
            part_root = root_path
            label = root_label
        else:
            part_root = root_path / subtrees[0]
            label = f"{root_label}/{subtrees[0]}"

        repo = source.Repository.from_directory(
            part_root,
            label,
            exclude_globs=tuple(partition["exclude_globs"])
        )
        report = catalog.import_project(part_root, repo, label=label, decision="keep_separate")
        stratum = partition["stratum"]
        catalog.set_stratum(
            report["graph_id"],
            stratum["role"],
            stratum["trust_tier"],
            stratum["modality"]
        )
        results.append({
            "key": key,
            "graph_id": report["graph_id"],
            "root": str(part_root),
            "snapshot_id": report["ingestion"]["snapshot_id"],
        })

    return results
