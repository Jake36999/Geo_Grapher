"""Apply explicit human folder decisions through the existing immutable ingester."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from .model import canonical, digest
from .pipeline import ingest
from .source import Repository, valid_path
from .store import SnapshotStore

STRATA = {
    'own-current': ('current', 'gold', 'code'), 'own-legacy': ('legacy', 'bronze', 'code'),
    'own-docs': ('docs', 'silver', 'doc'), 'research-docs': ('third_party', 'bronze', 'paper'),
    'third-party': ('third_party', 'bronze', 'code'), 'data': ('data', 'bronze', 'doc'),
    'logs/transcripts': ('transcripts', 'bronze_transcript', 'transcript'),
}


def stratum_for(card):
    role, trust, modality = STRATA[card['decision']['purpose']]
    if role == 'third_party' and card['decision']['purpose'] == 'third-party':
        observed = card.get('partition', {}).get('stratum', {}).get('modality')
        if observed in {'code', 'doc', 'paper'}: modality = observed
    return role, trust, modality


def authorship_for(card):
    decision = card['decision']
    derived = {'own-current': 'owner_created', 'own-legacy': 'owner_created',
               'own-docs': 'owner_created', 'research-docs': 'third_party',
               'third-party': 'third_party'}.get(decision['purpose'])
    explicit = decision.get('authorship')
    if derived and explicit and explicit != derived:
        raise ValueError('FOLDER_AUTHORSHIP: purpose and authorship disagree')
    result = derived or explicit
    if result not in {'owner_created', 'generated', 'third_party'}:
        raise ValueError('FOLDER_AUTHORSHIP: data/transcripts require explicit authorship')
    return result


def _reviewed(decision):
    """A person's decision, or the owning Librarian Core's agent-mode policy decision.

    The Core records accepted_by='agent-policy' with policy.mode='agent' only after checking
    the library's promotion.mode; this CLI is invoked by that Core alone.
    """
    if decision.get('accepted_by') == 'person':
        return True
    policy = decision.get('policy')
    return (decision.get('accepted_by') == 'agent-policy' and isinstance(policy, dict)
            and policy.get('mode') == 'agent')


def apply_review(catalog, request):
    library = str(Path(request['library']).resolve()); groups = defaultdict(list)
    decisions = request['decisions']; roots = []
    for card in decisions:
        decision = card['decision']; relative = card['path']
        if (card.get('status') != 'accepted' or not _reviewed(decision)
                or (relative != '.' and not valid_path(relative))):
            raise ValueError('FOLDER_REVIEW_REQUIRED: explicit person decisions with safe folder paths')
        root = Path(card['source_root']).resolve(); target = root if relative == '.' else root / relative
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            raise ValueError('FOLDER_SCOPE: source folder escaped its reviewed root')
        purpose = decision['purpose']
        if purpose not in STRATA and purpose != 'exclude':raise ValueError('FOLDER_PURPOSE')
        roots.append((target.resolve(), card))
        if purpose != 'exclude':groups[decision['graph']].append((target.resolve(), card))
    # Validate the entire assignment before creating a graph or reading source bodies.
    existing_by_label = defaultdict(list)
    for graph in catalog.graphs(): existing_by_label[graph['label'].casefold()].append(graph)
    for label, members in groups.items():
        if len({authorship_for(c) for _, c in members}) != 1:
            raise ValueError('GROUP_STRATUM_CONFLICT: different authorship cannot share a graph')
        if len({stratum_for(c) for _, c in members}) != 1:
            raise ValueError('GROUP_STRATUM_CONFLICT: own and external content cannot share a graph')
        choices = existing_by_label[label.casefold()]
        if len(choices) > 1:raise ValueError('GRAPH_LABEL_AMBIGUOUS: choose a unique graph label')
        if choices:
            if not catalog.owns_store(choices[0]):raise ValueError('GRAPH_ASSIGNMENT_READ_ONLY: registered external stores cannot be expanded')
            prior = json.loads(choices[0]['profile_json'])
            wanted = stratum_for(members[0][1])
            original = prior.get('stratum', dict(role='current', trust_tier='gold', modality='code'))
            if tuple(original.get(k) for k in ('role','trust_tier','modality')) != wanted:
                raise ValueError('GROUP_STRATUM_CONFLICT: the existing graph has another stratum; choose a separate graph')
    result = []
    for label, members in sorted(groups.items()):
        prior_graph = next(iter(existing_by_label[label.casefold()]), None)
        prior_profile = json.loads(prior_graph['profile_json']) if prior_graph else {}
        gid = prior_graph['graph_id'] if prior_graph else 'g_' + digest('reviewed-folder-group-v1', library, label)[:24]
        retained = prior_profile.get('retained_sources', [])
        if prior_graph and prior_profile.get('graph_kind', 'project') in {'project','derived'}:
            retained = [dict(root=prior_graph['root_path'], repo_id=gid,
                exclude_globs=prior_profile.get('exclude_globs', []), source_roots=prior_profile.get('source_roots', ['']),
                include_globs=prior_profile.get('include_globs', ['*']))]
        for old in retained:
            target = Path(old['root']).resolve()
            if not any(path == target for path, _ in members):
                members.append((target, dict(decision=members[0][1]['decision'])))
        repositories = []; sources = []; estimated = 100 * 1024 * 1024
        for target, card in sorted(members, key=lambda item: str(item[0])):
            excludes = [value for child, _ in roots if child != target and child.is_relative_to(target)
                        for value in (child.relative_to(target).as_posix(), child.relative_to(target).as_posix() + '/*')]
            excludes += ['librarian-app', 'librarian-app/*', 'test-results', 'test-results/*', '*.log', '*.blend*']
            original = next((r for r in retained if Path(r['root']).resolve() == target), {})
            excludes += original.get('exclude_globs', [])
            member_id = original.get('repo_id', gid + ':' + digest(str(target))[:12])
            repo = Repository.from_directory(target, member_id, exclude_globs=tuple(excludes),
                source_roots=tuple(original.get('source_roots', [''])), include_globs=tuple(original.get('include_globs', ['*'])))
            estimated += 20 * sum(len(b) for b in repo.files.values())
            repositories.append(repo); sources.append(dict(root=str(target), repo_id=member_id, exclude_globs=excludes))
        if shutil.disk_usage(catalog.path.parent).free - estimated < 5 * 1024**3:
            raise ValueError('DISK_RESERVE: estimated ingest would leave less than 5 GiB')
        database = Path(prior_graph['code_database']) if prior_graph else catalog.path.parent / 'graphs' / gid / 'code.sqlite'
        database.parent.mkdir(parents=True, exist_ok=True)
        with catalog.import_lock, SnapshotStore(database) as store:
            report = ingest(store, repositories, stage=3, reuse_complete=True)
            # Historical snapshots keep their ownership; current scope is the published snapshot.
            owners = [r[0] for r in store.connection.execute("SELECT DISTINCT repo_id FROM snapshots WHERE repo_id<>'@workspace' ORDER BY repo_id")]
        role, trust, modality = stratum_for(members[0][1])
        profile = dict(prior_profile)
        profile.update(graph_kind='reviewed_folder_group', owner_repo_ids=owners, retained_sources=retained, disabled=False,
                       source_roots_reviewed=sources, library=library, read_only=True,
                       stratum=dict(role=role, trust_tier=trust, modality=modality,
                                    authorship=authorship_for(members[0][1])))
        with catalog.lock, catalog.connection:
            catalog.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,NULL,?,?,?) '
                'ON CONFLICT(graph_id) DO UPDATE SET snapshot_id=excluded.snapshot_id,profile_json=excluded.profile_json',
                (gid, prior_graph['root_key'] if prior_graph else 'folder-group:' + gid,
                 prior_graph['root_path'] if prior_graph else library, label, str(database), report['snapshot_id'], canonical(profile),
                 datetime.now(timezone.utc).isoformat()))
        result.append(dict(graph_id=gid, label=label, snapshot_id=report['snapshot_id'],
                           stratum=profile['stratum'], folders=[str(p) for p, _ in members],
                           coverage='supported code and text; PDFs use the existing paper ingestion workflow'))
    # Exclude, never delete: retire empty reviewed groups from research visibility.
    active = {g['graph_id'] for g in result}
    with catalog.lock, catalog.connection:
        for graph in catalog.graphs():
            profile = json.loads(graph['profile_json'])
            if profile.get('graph_kind') == 'reviewed_folder_group' and profile.get('library') == library and graph['graph_id'] not in active:
                profile.update(disabled=True, exclusion_reason='no accepted non-excluded folders')
                catalog.connection.execute('UPDATE graphs SET profile_json=? WHERE graph_id=?', (canonical(profile), graph['graph_id']))
    return dict(geographer_version='0.2.0', graphs=result)
