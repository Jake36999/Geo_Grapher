"""No-model readiness tickets: a paid evaluator cannot silently skip preflight."""
import hashlib
import json
from pathlib import Path

REQUIRED={'profile_registry','real_tool_calls','scope','structured_withheld','batch_path'}

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
