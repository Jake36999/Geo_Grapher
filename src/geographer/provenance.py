"""Graph provenance is an access boundary, not a ranking suggestion."""
import json


def stratum(graph):
    return json.loads(graph['profile_json']).get('stratum', {})


def third_party(graph):
    return stratum(graph).get('role') in {'third_party', 'external_reference', 'research_docs'}


def metadata(graph):
    return dict(provenance='third_party', cite_as=graph['label'] + '/root') if third_party(graph) else {}


def annotate_flat(graph, out):
    if not third_party(graph): return out
    out.update(metadata(graph))
    data = out.get('result', {}).get('data', {})
    for rows in [out.get('entities', []), *[data.get(key, []) for key in
                 ('nodes','hits','results','matches','chunks','calls_constants')]]:
        for row in rows:
            row['provenance'] = 'third_party'
            eid = row.get('entity_id')
            row.setdefault('cite_as', graph['label'] + '/entity:' + eid if eid else graph['label'] + '/root')
    return out


def enforce_reader(graph, *, consumer_role='lead', profile=None):
    if json.loads(graph['profile_json']).get('disabled'):
        raise ValueError('GRAPH_EXCLUDED: its reviewed folders are excluded; immutable history is retained')
    if third_party(graph) and (consumer_role not in {'lead', 'research_helper'} or profile == 'tier3_leaf'):
        raise ValueError('THIRD_PARTY_SCOPE: only lead and research-helper research routes may read this graph')


def bridge_boundary(catalog, left, right):
    return third_party(catalog.graph(left)) != third_party(catalog.graph(right))


def mcp_entries(catalog, command):
    """Generate opt-in stdio configurations; never launch, accept or change a binding."""
    groups = {'own': [], 'reference': []}
    for graph in catalog.graphs():
        if json.loads(graph['profile_json']).get('disabled'): continue
        groups['reference' if third_party(graph) else 'own'].append(graph['graph_id'])
    def entry(ids, role, preset):
        return dict(command=command[0], args=[*command[1:], 'serve-graphs', '--transport', 'stdio',
            '--catalog', str(catalog.path), '--consumer-role', role, '--tools', preset,
            *[value for gid in sorted(ids) for value in ('--graph-id', gid)]])
    result = {}
    if groups['own']: result['geo-own-packets'] = entry(groups['own'], 'clerk', 'lead')
    if groups['reference']: result['geo-references'] = entry(groups['reference'], 'research_helper', 'cross')
    if groups['own'] or groups['reference']:
        result['geo-lead'] = entry(groups['own'] + groups['reference'], 'lead', 'lead')
    return result
