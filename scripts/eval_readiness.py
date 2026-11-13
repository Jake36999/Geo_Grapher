"""No-model readiness tickets: a paid evaluator cannot silently skip preflight."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

REQUIRED={'profile_registry','real_tool_calls','scope','structured_withheld','batch_path','recovery_loop','mcp_metadata','step_limit_recovery'}


def graph_scope(catalog,labels):
    scope={}
    with closing(sqlite3.connect(Path(catalog).resolve().as_uri()+'?mode=ro',uri=True)) as c:
        for label in sorted(labels):
            rows=c.execute('SELECT graph_id,snapshot_id,code_database FROM graphs WHERE label=?',(label,)).fetchall()
            if len(rows)!=1 or not rows[0][2]:raise ValueError('Frozen graph scope is unavailable or ambiguous')
            scope[label]=dict(zip(('graph_id','snapshot_id','code_database'),rows[0]))
    return scope

def fingerprint(paths):
    return {str(Path(p).resolve()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}

def ticket(config,checks,paths):
    if not REQUIRED<=checks.keys() or any(checks[k] is not True for k in REQUIRED):
        raise ValueError('No-model dry run did not pass every required check')
    return dict(config=config,checks=checks,inputs=fingerprint(paths),paid_provider_calls=0)

def require(value,config):
    if not isinstance(value,dict) or value.get('config')!=config or value.get('paid_provider_calls')!=0:
        raise ValueError('A clean no-model dry run is mandatory before paid dispatch')
    if not REQUIRED<=value.get('checks',{}).keys() or any(value['checks'][k] is not True for k in REQUIRED):
        raise ValueError('No-model dry-run checks are incomplete')
    if not value.get('inputs') or fingerprint(value['inputs'])!=value['inputs']:
        raise ValueError('Inputs changed after the no-model dry run')
    if 'catalog' in config:
        frozen=config.get('graph_scope')
        if not frozen or graph_scope(config['catalog'],frozen)!=frozen:
            raise ValueError('Frozen snapshot/graph scope changed after the no-model dry run')
