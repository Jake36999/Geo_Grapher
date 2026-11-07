"""Strict runtime models derived from the authoritative TypeScript declarations."""
from __future__ import annotations

from .resources import resource_root

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any, Literal, Union

import jsonschema
from pydantic import AfterValidator, ConfigDict, Field, TypeAdapter, create_model

from .model import canonical, digest


class WireContracts:
    def __init__(self, root: Path | None = None):
        root = root or resource_root() / "contracts"
        self.document = json.loads((root/"generated/geographer.wire.schema.json").read_text(encoding="utf-8"))
        if hashlib.sha256((root/"geographer.wire.d.ts").read_bytes()).hexdigest() != self.document["contract_sha256"]:
            raise RuntimeError("Wire contracts changed; run npm run contracts")
        self.definitions = self.document["$defs"]
        self.cache = {}
        self.adapters = {}
        for operation, schemas in self.document["operations"].items():
            for direction, schema in schemas.items():
                self.adapters[(operation,direction)] = TypeAdapter(self._type(schema))

    def schema(self, operation, direction):
        root=self.document['operations'][operation][direction];needed={}
        def collect(value):
            if isinstance(value,dict):
                if '$ref' in value:
                    name=value['$ref'].rsplit('/',1)[-1]
                    if name not in needed:needed[name]=self.definitions[name];collect(needed[name])
                else:
                    for v in value.values():collect(v)
            elif isinstance(value,list):
                for v in value:collect(v)
        collect(root)
        return {"$schema":"https://json-schema.org/draft/2020-12/schema",
                **root,"$defs":needed}

    def _type(self, schema):
        if "$ref" in schema:
            name=schema["$ref"].rsplit("/",1)[-1]
            if name not in self.cache:
                self.cache[name]=self._type(self.definitions[name])
            return self.cache[name]
        if "const" in schema:
            return Literal[schema["const"]]
        if "anyOf" in schema:
            return Union[tuple(self._type(s) for s in schema["anyOf"])]
        kind=schema["type"]
        if kind=="object":
            if 'properties' not in schema:return dict[str,self._type(schema['additionalProperties'])]
            required=set(schema.get('required',()))
            fields={name:(self._type(value),... if name in required else None) for name,value in schema["properties"].items()}
            return create_model("Wire_"+digest(schema)[:12],__config__=ConfigDict(extra="forbid",strict=True,allow_inf_nan=False),**fields)
        if kind=="array":
            if "prefixItems" in schema:
                return tuple[tuple(self._type(s) for s in schema["prefixItems"])]
            base=list[self._type(schema["items"])]
            return Annotated[base,Field(min_length=schema.get("minItems"),max_length=schema.get("maxItems"))]
        base={"string":str,"integer":int,"number":float,"boolean":bool,"null":type(None)}[kind]
        constraints={target:schema[source] for source,target in (("minimum","ge"),("maximum","le"),
            ("exclusiveMinimum","gt"),("exclusiveMaximum","lt"),("minLength","min_length"),
            ("maxLength","max_length"),("pattern","pattern")) if source in schema}
        if constraints:
            base=Annotated[base,Field(**constraints)]
        if "x-maxUtf8Bytes" in schema:
            maximum=schema["x-maxUtf8Bytes"]
            def check(value):
                if len(value.encode("utf-8"))>maximum:
                    raise ValueError("UTF-8 byte length exceeds contract limit")
                return value
            base=Annotated[base,AfterValidator(check)]
        return base

    def validate(self, operation, direction, value):
        serialised=canonical(value)
        serialised.encode("utf-8")  # Reject lone surrogates, not silently replace identity.
        jsonschema.Draft202012Validator(self.schema(operation,direction)).validate(value)
        model=self.adapters[(operation,direction)].validate_json(serialised,strict=True)
        result=model.model_dump(mode="json",exclude_unset=True) if hasattr(model,"model_dump") else model
        if direction=="request":
            self._request_semantics(result)
        return result

    @staticmethod
    def _request_semantics(value):
        if "start_line" in value:
            a,b=value["start_line"],value["end_line"]
            if (a is None)!=(b is None) or a is not None and b<a:
                raise ValueError("Source range must be two ordered lines or two nulls")
        if "projection_id" in value:
            if (value["projection_id"] is None)==(value["relationship_id"] is None):
                raise ValueError("Specify exactly one projection or raw relationship")
            if value["evidence_cursor"] is not None and (value["relationship_id"] is None or value["cursor"] is not None):
                raise ValueError("Evidence cursor requires a raw relationship and no witness cursor")
        if "filter" in value:
            f=value["filter"]
            window=f["runtime_window"]
            if "runtime" in f["families"] and window is None:
                raise ValueError("Runtime family requires a collection window")
            if window:
                from datetime import datetime
                for key in ("start","end"):
                    if not window[key].endswith("Z"):
                        raise ValueError("Runtime timestamps must be RFC3339 UTC Z")
                    datetime.fromisoformat(window[key].replace("Z","+00:00"))
                if window["start"]>=window["end"]:
                    raise ValueError("Runtime window must have start < end")
        if "camera" in value:
            import math
            camera=value["camera"]
            if camera["far"]<=camera["near"] or math.dist(camera["eye"],camera["target"])<1e-12 or math.dist(camera["up"],[0,0,0])<1e-12:
                raise ValueError("Degenerate camera")
