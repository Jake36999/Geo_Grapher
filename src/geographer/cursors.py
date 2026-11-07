"""Snapshot-bound HMAC cursors backed by bounded LRU/TTL query plans."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass,field

from .model import canonical,digest


class InvalidCursor(ValueError):pass


@dataclass
class Plan:
    snapshot_id:str
    query_digest:str
    view_id:str|None
    collection:str
    units:list
    mandatory:dict
    totals:dict
    expires:float
    pages:dict=field(default_factory=lambda:{"start":[]})
    evidence_plans:dict=field(default_factory=dict)


class CursorPlans:
    def __init__(self,secret=None,max_plans=256,ttl_seconds=900,clock=time.monotonic,max_units=100000,max_total_units=200000):
        self.secret=secret or secrets.token_bytes(32)
        if len(self.secret)<32:raise ValueError("Cursor secret must be at least 32 bytes")
        self.max_plans=max_plans;self.ttl=ttl_seconds;self.clock=clock;self.max_units=max_units
        self.max_total_units=max_total_units
        self.plans=OrderedDict()

    @staticmethod
    def _encode(data):return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(text):return base64.urlsafe_b64decode(text+"="*((-len(text))%4))

    def _prune(self):
        for key in list(self.plans):
            if self.plans[key].expires<=self.clock():self.plans.pop(key)
        total=sum(len(p.units) for p in self.plans.values())
        while self.plans and (len(self.plans)>self.max_plans or total>self.max_total_units):
            _,removed=self.plans.popitem(last=False);total-=len(removed.units)

    def create(self,snapshot_id,query_digest,view_id,collection,units,mandatory,totals):
        self._prune()
        if len(units)>min(self.max_units,self.max_total_units):raise ValueError("Query plan exceeds bounded retention limit")
        key=(snapshot_id,query_digest)
        if key not in self.plans:
            self.plans[key]=Plan(snapshot_id,query_digest,view_id,collection,units,mandatory,totals,self.clock()+self.ttl)
        self.plans.move_to_end(key);self._prune()
        return self.plans[key]

    def cursor(self,plan,delivered,*,commit=True):
        if commit:
            self.plans[(plan.snapshot_id,plan.query_digest)]=plan
            self.plans.move_to_end((plan.snapshot_id,plan.query_digest));self._prune()
        delivered=sorted(set(delivered))
        token=digest(delivered)
        # Bounded page checkpoints; replay is supported while retained, not forever.
        if commit and token not in plan.pages and len(plan.pages)>=256:
            removable=next((k for k in plan.pages if k!='start'),None)
            if removable:plan.pages.pop(removable)
        if commit:plan.pages[token]=delivered
        payload=canonical(dict(v=1,snapshot_id=plan.snapshot_id,query_digest=plan.query_digest,
                               view_id=plan.view_id,collection=plan.collection,after_id=token)).encode()
        return self._encode(payload)+"."+self._encode(hmac.digest(self.secret,payload,"sha256"))

    def initial_cursor(self,snapshot_id,query_digest,view_id,collection):
        payload=canonical(dict(v=1,snapshot_id=snapshot_id,query_digest=query_digest,view_id=view_id,
                               collection=collection,after_id="start")).encode()
        return self._encode(payload)+"."+self._encode(hmac.digest(self.secret,payload,"sha256"))

    def resume(self,cursor,snapshot_id,query_digest):
        self._prune()
        try:
            if len(cursor.encode())>4096:raise ValueError()
            encoded,signature=cursor.split(".")
            payload=self._decode(encoded)
            if self._encode(payload)!=encoded or self._encode(self._decode(signature))!=signature:raise ValueError()
            if not hmac.compare_digest(self._decode(signature),hmac.digest(self.secret,payload,"sha256")):
                raise ValueError()
            record=json.loads(payload)
            if set(record)!={"v","snapshot_id","query_digest","view_id","collection","after_id"} or record["v"]!=1:
                raise ValueError()
            if record["snapshot_id"]!=snapshot_id or record["query_digest"]!=query_digest:raise ValueError()
            key=(snapshot_id,query_digest)
            if record["after_id"]=="start" and key not in self.plans:return None,[]
            plan=self.plans[key]
            if record["view_id"]!=plan.view_id or record["collection"]!=plan.collection:raise ValueError()
            delivered=plan.pages[record["after_id"]]
            self.plans.move_to_end(key)
            return plan,list(delivered)
        except (KeyError,ValueError,TypeError,UnicodeError,json.JSONDecodeError) as exc:
            raise InvalidCursor("Invalid, expired or evicted cursor; restart the query") from exc
