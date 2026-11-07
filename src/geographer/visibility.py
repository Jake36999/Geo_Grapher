"""Shared visibility macros; v1 clients send their explicit expanded filters."""
from copy import deepcopy
import json
from .resources import resource_root
from .analysis import DEFAULT_FILTER

def visibility_presets():
    return json.loads((resource_root()/'contracts/visibility-presets.json').read_text(encoding='utf-8'))

def visibility_filter(name,current=None):
    preset=visibility_presets()[name]
    result=deepcopy(DEFAULT_FILTER if current is None else current)
    result.update(resolution_statuses=list(preset['resolution_statuses']),include_external=preset['include_external'])
    return result
