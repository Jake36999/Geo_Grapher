"""Offline byte-pair token counting and an explicitly conservative byte fallback."""
from __future__ import annotations

from .resources import resource_root

import hashlib
import math
import os
import threading
from pathlib import Path
import urllib.request
from collections import OrderedDict

import tiktoken
from tiktoken.load import load_tiktoken_bpe
import tiktoken_ext.openai_public as encoding_definitions

from .model import canonical

WEIGHTS={
    "o200k_base":"446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d",
    "cl100k_base":"223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7",
}


def cache_directory():
    return Path(os.environ.get("TIKTOKEN_CACHE_DIR",str(resource_root()/"assets/tiktoken")))


def weight_path(name, directory=None):
    return (directory or cache_directory())/(name+".tiktoken")


def cache_weights(directory=None):
    """Explicit setup command only; queries never call this function or the network."""
    directory=directory or cache_directory();directory.mkdir(parents=True,exist_ok=True)
    for name,expected in WEIGHTS.items():
        destination=weight_path(name,directory)
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()==expected:
            continue
        url=f"https://openaipublic.blob.core.windows.net/encodings/{name}.tiktoken"
        with urllib.request.urlopen(url,timeout=30) as response:
            data=response.read()
        if hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError("Encoding weight checksum mismatch")
        temporary=destination.with_suffix(".download")
        temporary.write_bytes(data);temporary.replace(destination)
    return {name:{"path":str(weight_path(name,directory)),"sha256":sha} for name,sha in WEIGHTS.items()}


class TokenizerUnavailable(ValueError):pass


class TokenCounter:
    _loaded={}
    _counts=OrderedDict()
    _count_lock=threading.RLock()

    def __init__(self,name="o200k_base",allow_byte_fallback=False,directory=None):
        if name not in WEIGHTS:raise ValueError("Unsupported encoding")
        self.name=name;self.encoding=None;self.sha=None
        p=weight_path(name,directory)
        if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==WEIGHTS[name]:
            key=(name,str(p.resolve()),WEIGHTS[name])
            if key not in self._loaded:
                # Read local ranks; use the installed official constructor only for its
                # regex/special-token definitions, replacing its loader locally.
                # No module-global monkeypatch: clone the function's globals instead.
                import types
                constructor=getattr(encoding_definitions,name)
                globals_copy=dict(constructor.__globals__)
                globals_copy["load_tiktoken_bpe"]=lambda *a,**kw:load_tiktoken_bpe(str(p),expected_hash=WEIGHTS[name])
                params=types.FunctionType(constructor.__code__,globals_copy)()
                self._loaded[key]=tiktoken.Encoding(**params)
            self.encoding=self._loaded[key];self.sha=WEIGHTS[name]
        elif not allow_byte_fallback:
            raise TokenizerUnavailable("Offline encoding weights missing or invalid; run geographer cache-tokenizers")

    @property
    def exact(self):return self.encoding is not None

    def count(self,value):
        text=canonical(value)
        raw=text.encode('utf-8')
        if not self.exact:return math.ceil(len(raw)/4)
        key=(self.name,hashlib.sha256(raw).digest())
        with self._count_lock:
            if key in self._counts:
                self._counts.move_to_end(key);return self._counts[key]
        count=len(self.encoding.encode_ordinary(text))
        with self._count_lock:
            self._counts[key]=count;self._counts.move_to_end(key)
            while len(self._counts)>16384:self._counts.popitem(last=False)
        return count

    def cost(self,value):
        return self.count(value) if self.exact else len(canonical(value).encode("utf-8"))

    def report(self,region,limit):
        return dict(limit_tokens=limit,tokenizer=self.name,count_method="tiktoken" if self.exact else "utf8_bytes_div4",
                    weights_digest=self.sha,used_tokens=self.count(region),accounting_upper_bound=self.cost(region),
                    guarantee="exact_payload" if self.exact else "byte_bound",counted_region="budgeted_json")
