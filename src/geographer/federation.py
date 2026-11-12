"""Provenance-calibrated envelope selection for federated search (pc-mckp-v1).

Utilities are per graph and are never compared as retrieval scores: each graph
keeps its own ranking. They only decide which whole envelope (full, compact or
none) fits the shared token budget."""
from __future__ import annotations
from dataclasses import dataclass
import itertools
import math
import re

TIER_WEIGHT={'gold':1.00,'gold_paper':.95,'silver':.75,'bronze':.35,'bronze_transcript':.15}
MODALITIES=('code','doc','paper','legacy_doc','transcript')
_HISTORICAL={'legacy','deprecated','history','brainstorm','old'}
_PHI={'identifier':(1.25,1.00,.60),'conceptual':(1.05,1.20,.70),'historical':(1.00,1.00,1.15)}
_IDENTIFIER=re.compile(r'[A-Za-z_][\w.]*\(?\)?')


@dataclass(frozen=True)
class Candidate:
    graph_id:str
    tier:str  # 'full' or 'compact'; omission is implicit (0 tokens, 0 utility)
    tokens:int
    utility:int


def intent(query):
    if _HISTORICAL&set(re.findall(r'\w+',query.lower())):return 'historical'
    q=query.strip()
    if _IDENTIFIER.fullmatch(q) and ('_' in q or '.' in q or re.search(r'[a-z0-9][A-Z]',q)):return 'identifier'
    return 'conceptual'


def _phi(kind,modality):
    column=0 if modality=='code' else 2 if modality in {'legacy_doc','transcript'} else 1
    return _PHI[kind][column]


def utility(trust_tier,modality,intent,store_mb,hit_ranks,n_exact):
    if trust_tier not in TIER_WEIGHT:raise ValueError(f'Unknown trust tier {trust_tier!r}')
    if modality not in MODALITIES:raise ValueError(f'Unknown modality {modality!r}')
    psi=1/(1+.25*math.log(1+max(0.,store_mb)))
    recall=12*sum(1/(60+i) for i in list(hit_ranks)[:5])+.4*math.log(1+n_exact)
    return math.floor(round(10000*TIER_WEIGHT[trust_tier]*_phi(intent,modality)*psi*recall,6))


def select(candidates,budget):
    """Exact choice of one tier per graph maximising (sum U, -sum tokens), within budget.

    Ties break towards the lexicographically smallest sorted (graph_id, tier)
    assignment (tier order compact < full < omit), so the result cannot depend on
    argument order."""
    options={}
    for c in candidates:options.setdefault(c.graph_id,{})[c.tier]=c
    graphs=sorted(options)
    choices=[[None,*(options[g][t] for t in sorted(options[g]))] for g in graphs]
    best=None;best_key=None
    for combo in itertools.product(*choices):
        tokens=sum(c.tokens for c in combo if c)
        if tokens>budget:continue
        # Tie-break: lexicographically smallest assignment, tier order compact < full < omit.
        key=(-sum(c.utility for c in combo if c),tokens,tuple((g,c.tier if c else 'omit') for g,c in zip(graphs,combo)))
        if best_key is None or key<best_key:best_key=key;best=combo
    if best is None:best=(None,)*len(graphs)
    return {g:(c.tier if c else 'omit') for g,c in zip(graphs,best)}
