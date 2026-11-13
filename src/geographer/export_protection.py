"""
Source-derived export protection memo for the Geo‑Grapher project.
Scans ``source-bytes-v1`` analysis records to discover statically declared
``__all__`` exports and paths that require runtime-only protection.
Caches the result as ``helper-export-protection-v1`` in *graph.analyses*.
"""
import ast
import base64


def export_protection(graph) -> dict:
    """
    Return ``{'exported_names': [...], 'protected_paths': [...]}``,
    either from a cached analysis or by scanning Python source files.

    """
    cache_key = "helper-export-protection-v1"
    if cache_key in graph.analyses:
        return graph.analyses[cache_key]["result"]

    exported_names: set[str] = set()
    protected_paths: set[str] = set()

    # collect and sort relevant source records for deterministic iteration
    records = [
        r
        for r in graph.analyses.values()
        if r.get("algorithm_version") == "source-bytes-v1"
    ]
    records.sort(
        key=lambda r: (
            r["result"].get("rel_path", ""),
            r["scope"].get("entity_id", ""),
        )
    )

    for record in records:
        scope = record["scope"]
        entity_id = scope["entity_id"]
        entity = graph.entities.get(entity_id)
        if entity is None or entity.kind != "file" or entity.language != "python":
            continue

        rel_path = record["result"]["rel_path"]
        source_bytes = base64.b64decode(record["result"]["bytes_base64"])
        if b"__all__" not in source_bytes:
            continue

        try:
            tree = ast.parse(source_bytes)
        except (UnicodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            writes=(isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__all__' for t in node.targets) or
                isinstance(node,(ast.AnnAssign,ast.AugAssign)) and isinstance(node.target,ast.Name) and node.target.id=='__all__')
            mutates=isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='__all__'
            if writes or mutates:
                try:
                    values=ast.literal_eval(node.value) if writes else None
                    if not isinstance(values,(list,tuple)) or any(not isinstance(v,str) for v in values):raise ValueError('Unknown exports')
                    exported_names.update(values)
                except (ValueError,TypeError):protected_paths.add(rel_path)

    result = {
        "exported_names": sorted(exported_names),
        "protected_paths": sorted(protected_paths),
    }

    graph.analyses[cache_key] = {
        "algorithm_version": cache_key,
        "scope": {},
        "result": result,
    }
    return result


