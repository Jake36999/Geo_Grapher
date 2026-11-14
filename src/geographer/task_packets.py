"""Deterministic task packets compiled from published snapshot evidence."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .analysis import DEFAULT_FILTER
from .actor import resolve_request_aliases
from .bridges import parse_ref, resolve_ref
from .tokens import TokenCounter

PROFILE_CEILINGS = {'tier3_leaf': 1200, 'tier2_forager': 1800, 'tier1_lead': 32768}


def check_profile(profile, limit):
    if profile is None:
        return
    if not isinstance(profile, str) or profile not in PROFILE_CEILINGS:
        raise ValueError('UNKNOWN_PROFILE')
    if type(limit) is int and limit > PROFILE_CEILINGS[profile]:
        raise ValueError('BUDGET_EXCEEDS_PROFILE: ' + profile)


def _request(sid, **fields):
    return dict(schema_version='1.1', request_id='task-packet', snapshot_id=sid,
                budget=dict(limit_tokens=32768, tokenizer='o200k_base', allow_byte_fallback=False),
                cursor=None, **fields)


def _query(service, operation, request):
    out = service.query(operation, request)
    if 'error' in out:
        raise ValueError(str(out['error']))
    return out


def _entity(service, row, ref, eid):
    sid = row['snapshot_id']; g = service.store.graph(sid); e = g.entities[eid]
    content = _query(service, 'get_entity_content', _request(sid, entity_id=eid,
        content_kind='documentation' if e.kind == 'fragment' else 'source',
        start_line=None, end_line=None, context_mode='range', context_radius=0))
    # A partial page is not a complete anchor. Fetch its continuation before packing.
    chunks = list(content['data']['chunks'])
    while content['data']['completeness'].get('next_cursor'):
        req = _request(sid, entity_id=eid, content_kind='documentation' if e.kind == 'fragment' else 'source',
                       start_line=None, end_line=None, context_mode='range', context_radius=0)
        req['cursor'] = content['data']['completeness']['next_cursor']
        content = _query(service, 'get_entity_content', req)
        chunks.extend(content['data']['chunks'])
    anchor = dict(ref=ref, cite_as=row['label'] + '/' + ref, kind=e.kind, qualified_name=e.qualified_name,
        source=dict(rel_path=e.rel_path, start_line=e.start_line, end_line=e.end_line),
        text=''.join(c['text'] for c in chunks))
    arch = _query(service, 'get_architecture_context', _request(sid, focus_id=eid,
        grouping=dict(mode='atomic'), context_radius=1,
        filter={**DEFAULT_FILTER, 'resolution_statuses': ['exact', 'candidate']},
        pins=[], qi=dict(enabled=False, max_diameter=2)))
    data = arch['data']; scope = data['identity_scope']
    def decode(value, key):
        return resolve_request_aliases(service, service._context(sid), dict(snapshot_id=sid,
            view_id=data['view_id'], alias_scope=scope, **{key: value}))[key]
    boundary = []
    for rel in data['relationships']:
        a, b = decode(rel['source'], 'entity_id'), decode(rel['target'], 'entity_id')
        owners = {a, b} | {g.entities[v].parent_id for v in (a, b) if v in g.entities and g.entities[v].kind == 'scope_atom'}
        if eid in owners:
            rid = decode(rel['id'], 'projection_id')
            boundary.append(dict(**{'from': a, 'to': b}, subtype=rel['subtype'],
                                 cite_as=row['label'] + '/relationship:' + rid))
    return anchor, boundary


def _paper(row, ref):
    kind, p = parse_ref(ref)
    if kind == 'root':
        text = row['label']; title = text
    else:
        with sqlite3.connect(Path(row['paper_database']).resolve().as_uri() + '?mode=ro', uri=True) as con:
            if kind == 'claim':
                text = con.execute('SELECT text FROM read_claims WHERE id=? AND doc_id=?', (p['claim'], p['doc'])).fetchone()[0]
                title = ref
            elif kind == 'concept':
                text = con.execute('SELECT canonical_name FROM read_concepts WHERE id=?', (p['concept'],)).fetchone()[0]
                title = text
            elif kind == 'section':
                text = con.execute('SELECT text FROM sections WHERE id=?', (p['section'],)).fetchone()[0]
                title = ref
            else:
                title, abstract = con.execute('SELECT title,abstract_summary FROM read_documents WHERE id=?', (p['doc'],)).fetchone()
                text = title + '\n' + (abstract or '')
    return dict(ref=ref, cite_as=row['label'] + '/' + ref, kind=kind, qualified_name=title,
                source=dict(rel_path=None, start_line=None, end_line=None), text=text or ''), []


def compile_packet(router, graph_id, anchors, instruction, *, profile='tier3_leaf', upstream=()):
    check_profile(profile, 0)
    if profile is None:
        raise ValueError('UNKNOWN_PROFILE')
    if not isinstance(instruction, str) or not isinstance(anchors, list) or not 1 <= len(anchors) <= 8:
        raise ValueError('PACKET_SHAPE')
    if not isinstance(upstream, (list, tuple)):
        raise ValueError('PACKET_SHAPE')
    gid = router.resolve(graph_id); router.permit(gid)
    from .provenance import enforce_reader, metadata, third_party
    enforce_reader(router.catalog.graph(gid), consumer_role=router.consumer_role, profile=profile)
    counter = TokenCounter(); limit = PROFILE_CEILINGS[profile]
    if counter.count(instruction) > limit // 4:
        raise ValueError('INSTRUCTION_TOO_LONG')
    with router.catalog.lock, router.lease(gid) as service, service.lock:
        row = router.catalog.graph(gid)
        for ref in anchors:
            try:
                resolve_ref(router.catalog, gid, ref)
            except (ValueError, TypeError):
                raise ValueError('BRIDGE_ENDPOINT_UNRESOLVED: ' + str(ref)) from None
        candidates, boundary = [], {}
        for ref in anchors:
            kind, parts = parse_ref(ref)
            a, bs = _entity(service, row, ref, parts['entity']) if kind == 'entity' else _paper(row, ref)
            candidates.append(a)
            for b in bs:
                boundary[b['cite_as']] = b

        def valid_cite(cite):
            if not isinstance(cite, str) or not cite.startswith(row['label'] + '/'):
                return False
            try:
                ref=cite[len(row['label']) + 1:]
                if ref.startswith('relationship:'):
                    return service.store.connection.execute('SELECT 1 FROM quotient_projections WHERE snapshot_id=? AND projection_id=?',
                        (row['snapshot_id'],ref[len('relationship:'):])).fetchone() is not None
                resolve_ref(router.catalog, gid, ref)
                return True
            except ValueError:
                return False

        records, dropped = [], 0
        for rec in upstream:
            if not isinstance(rec, dict) or not isinstance(rec.get('task_id'), str) or not valid_cite(rec.get('cite')):
                dropped += 1; continue
            try:
                resolve_ref(router.catalog, gid, rec.get('ref'))
            except (ValueError, TypeError):
                dropped += 1; continue
            clean = dict(task_id=rec['task_id'], ref=rec['ref'], cite=rec['cite'],
                         origin='model_produced_citation_verified')
            for port in ('inputs', 'outputs'):
                clean[port] = []
                if not isinstance(rec.get(port), list):
                    dropped += 1; continue
                for item in rec[port]:
                    if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not valid_cite(item.get('cite')):
                        dropped += 1; continue
                    clean[port].append(dict(name=item['name'][:80], cite=item['cite']))
            records.append(clean)
        records.sort(key=lambda r: (r['task_id'], r['ref']))
        if third_party(row):
            for item in candidates + list(boundary.values()):item['provenance']='third_party'
        out = dict(packet_version='task-packet-v1', graph_id=gid, graph_label=row['label'],
            snapshot_id=row['snapshot_id'], profile=profile, limit_tokens=limit, used_tokens=0,
            instruction=instruction, upstream=[], upstream_dropped=dropped, upstream_omitted=len(records),
            anchors=[], boundary=[], handles=[], **metadata(row))

        def recount():
            handles = {item['cite_as'] for key in ('anchors', 'boundary') for item in out[key]}
            for rec in out['upstream']:
                handles.add(rec['cite'])
                handles.update(p['cite'] for k in ('inputs', 'outputs') for p in rec[k])
            out['handles'] = sorted(handles)
            out['upstream_omitted'] = len(records) - len(out['upstream'])
            for _ in range(12):
                count = counter.count(out)
                if count == out['used_tokens']:
                    return count
                out['used_tokens'] = count
            raise ValueError('TOKEN_COUNT_UNSTABLE')

        base = recount()
        remaining = limit - base
        if remaining < 0:
            raise ValueError('BUDGET_TOO_SMALL')
        # Price each section including duplicate handles and metadata; unused shares flow forward.
        instruction_cost = counter.count(instruction)
        allowance = min(remaining, max(0, limit // 4 - instruction_cost))
        for section, items, extra in (('upstream', records, 0), ('anchors', candidates, limit * 55 // 100),
                                      ('boundary', [boundary[k] for k in sorted(boundary)], limit * 20 // 100)):
            allowance = min(limit - recount(), allowance + extra)
            section_start = recount()
            for item in items:
                out[section].append(item)
                if recount() - section_start > allowance or out['used_tokens'] > limit:
                    out[section].pop(); recount(); break
            allowance -= recount() - section_start
        for section in ('boundary', 'anchors', 'upstream'):
            while out[section] and (recount() > limit or router.max_result_chars and len(json.dumps(out, ensure_ascii=False)) > router.max_result_chars):
                out[section].pop()
        recount()
        if out['used_tokens'] > limit:
            raise ValueError('BUDGET_TOO_SMALL')
        if router.max_result_chars and len(json.dumps(out, ensure_ascii=False)) > router.max_result_chars:
            raise ValueError('RESULT_TOO_LARGE')
        return out
