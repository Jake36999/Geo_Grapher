"""Agent coverage metadata for Geo-Grapher responses."""

from typing import Any, Dict, Optional, Tuple
import hashlib
import json


def coverage_metadata(
    operation: str,
    data: Dict[str, Any],
    expected_range: Optional[Tuple[int, int]]
) -> Dict[str, Any]:
    """Generate coverage metadata for agent responses."""
    if operation == "get_entity_content":
        return _content_coverage(data, expected_range)
    elif operation == "search_entities":
        return _search_coverage(data)
    else:
        return {"coverage": [], "coverage_truncated": False}


def _content_coverage(
    data: Dict[str, Any],
    expected_range: Optional[Tuple[int, int]]
) -> Dict[str, Any]:
    """Handle content coverage for get_entity_content."""
    chunks = data.get("chunks", [])
    entity_id = data.get("entity_id", "")
    completeness_truncated = data.get("completeness", {}).get("truncated", False)

    # Sort chunks by start_line then text
    sorted_chunks = sorted(chunks, key=lambda c: (c["source"]["start_line"], c["text"]))

    # Merge consecutive non-overlapping ranges
    merged_ranges = []
    for chunk in sorted_chunks:
        start = chunk["source"]["start_line"]
        end = chunk["source"]["end_line"]
        text = chunk["text"]

        # Check if we can merge with last range
        if merged_ranges and merged_ranges[-1]["end_line"] + 1 == start:
            merged_ranges[-1]["end_line"] = end
            merged_ranges[-1]["texts"].append(text)
        else:
            merged_ranges.append({
                "start_line": start,
                "end_line": end,
                "texts": [text]
            })

    complete = (expected_range is not None and len(merged_ranges) == 1 and
                merged_ranges[0]['start_line'] == expected_range[0] and
                merged_ranges[0]['end_line'] == expected_range[1])
    # Generate coverage entries
    coverage = []
    for r in merged_ranges:
        content = "".join(r["texts"]).encode("utf-8")
        sha256 = hashlib.sha256(content).hexdigest()

        # Determine truncation status
        truncated = (
            completeness_truncated or
            not complete
        )

        coverage.append({
            "entity_id": entity_id,
            "start_line": r["start_line"],
            "end_line": r["end_line"],
            "truncated": truncated,
            "sha256": sha256
        })

    # Apply 16-item limit
    coverage_truncated = len(coverage) > 16
    return {
        "coverage": coverage[:16],
        "coverage_truncated": coverage_truncated
    }


def _search_coverage(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle coverage for search_entities."""
    nodes = data.get("nodes", [])
    hits = data.get("hits", [])
    completeness_truncated = data.get("completeness", {}).get("truncated", False)

    # Create mapping of entity_id to hit for ordering
    node_map = {node["entity_id"]: node for node in nodes}

    # Order by hits first, then remaining nodes
    ordered_entities = []
    seen = set()

    # Add hits in order
    for hit in hits:
        entity_id = hit["entity_id"]
        if entity_id in node_map and entity_id not in seen:
            ordered_entities.append((node_map[entity_id], hit))
            seen.add(entity_id)

    # Add remaining nodes sorted by entity_id
    remaining_nodes = [node for node in nodes if node["entity_id"] not in seen]
    remaining_nodes.sort(key=lambda n: n["entity_id"])
    for node in remaining_nodes:
        ordered_entities.append((node, None))

    # Generate coverage entries
    coverage = []
    for node, hit in ordered_entities[:16]:
        entity_id = node["entity_id"]
        raw_json = json.dumps(
            {"node": node, "hit": hit},
            sort_keys=True,
            ensure_ascii=False,
            separators=(',', ':')
        ).encode("utf-8")
        sha256 = hashlib.sha256(raw_json).hexdigest()

        coverage.append({
            "entity_id": entity_id,
            "start_line": None,
            "end_line": None,
            "truncated": completeness_truncated,
            "sha256": sha256
        })

    coverage_truncated = len(ordered_entities) > 16
    return {
        "coverage": coverage,
        "coverage_truncated": coverage_truncated
    }
