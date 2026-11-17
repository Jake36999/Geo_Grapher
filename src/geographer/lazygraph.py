"""Tables read from a snapshot store on demand, for the compact view form of a loaded graph.

A loaded graph used to hold every entity, relationship, evidence row, analysis result and fingerprint as
Python objects: 12-14 KB per entity, 5.4 GB for six Nonlinear Field Lab graphs (owner, 2026-11-17). A
frame, a hierarchy and a label read almost none of the evidence or analyses, so those tables are
`LazyTable`s: a dict that answers a point lookup, a key listing or a length from the store, and fills
itself completely, in the original order, the first time something needs the values. Whatever needs the
whole table therefore sees exactly what the eager load would have given it.

The rules that keep it a faithful dict:
- `[key]`, `.get`, `in`, `len`, iteration and `.keys()` do not fill the table when a keys query exists.
- `.values()`, `.items()`, comparison, copy and every mutator fill it first.
- After a fill it is an ordinary dict. `loaded` says which state it is in.
- A table read one row at a time more than POINT_LIMIT times fills itself: a safety valve, high enough that
  a person browsing never reaches it (a frame is a few hundred lookups, and a repeated key is read once).
- With a `default_factory` it behaves like a defaultdict: `[key]` on an absent key creates and keeps the default,
  `.get` does not.
Not thread-safe by itself: it is used under the owning service's lock, like the store connection.
"""
from __future__ import annotations

from collections.abc import KeysView
from typing import Any, Callable, Iterable

MISSING = object()
POINT_LIMIT = 50_000


class LazyTable(dict):
    def __init__(self, *, fill: Callable[[], Iterable[tuple[Any, Any]]],
                 keys: Callable[[], Iterable[Any]] | None = None,
                 point: Callable[[Any], Any] | None = None,
                 default_factory: Callable[[], Any] | None = None):
        super().__init__()
        self._fill_fn, self._keys_fn, self._point_fn, self._default = fill, keys, point, default_factory
        self.loaded = False
        self._keys: list | None = None
        self._keyset: set | None = None
        self._cache: dict = {}
        self._created: dict = {}          # defaults handed out for absent keys, kept as a defaultdict would
        self.point_reads = 0

    # -- state ------------------------------------------------------------------------------------
    def _load(self) -> None:
        if self.loaded:
            return
        dict.clear(self)
        for key, value in self._fill_fn():
            dict.__setitem__(self, key, value)
        for key, value in self._created.items():
            if not dict.__contains__(self, key):
                dict.__setitem__(self, key, value)
        self.loaded = True
        self._keys = self._keyset = None
        self._cache, self._created = {}, {}

    def _key_list(self) -> list:
        if self._keys is None:
            self._keys = list(self._keys_fn())
            self._keyset = set(self._keys)
        return self._keys

    # -- reads that need not fill -------------------------------------------------------------------
    def __iter__(self):
        if not self.loaded and self._keys_fn is not None:
            return iter(self._key_list())
        self._load()
        return dict.__iter__(self)

    def keys(self):
        return KeysView(self)

    def __len__(self) -> int:
        if not self.loaded and self._keys_fn is not None:
            return len(self._key_list())
        self._load()
        return dict.__len__(self)

    def __contains__(self, key) -> bool:
        if not self.loaded and self._keys_fn is not None:
            self._key_list()
            return key in self._keyset
        self._load()
        return dict.__contains__(self, key)

    def _point(self, key):
        """The value for `key` read on its own, MISSING if absent; None when the table must fill."""
        if self._point_fn is None:
            self._load()
            return None
        if key in self._cache:
            return self._cache[key]
        self.point_reads += 1
        if self.point_reads > POINT_LIMIT:
            self._load()
            return None
        value = self._point_fn(key)
        if value is not MISSING:
            self._cache[key] = value
        return value

    def __getitem__(self, key):
        if not self.loaded:
            value = self._point(key)
            if not self.loaded:
                if value is not MISSING:
                    return value
                if self._default is None:
                    raise KeyError(key)
                value = self._default()
                self._cache[key] = self._created[key] = value
                return value
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            if self._default is None:
                raise
            value = self._default()
            dict.__setitem__(self, key, value)
            return value

    def get(self, key, default=None):
        if not self.loaded:
            value = self._point(key)
            if not self.loaded:
                return default if value is MISSING else value
        return dict.get(self, key, default)


def _filling(name: str):
    base = getattr(dict, name)

    def method(self, *args, **kwargs):
        self._load()
        return base(self, *args, **kwargs)
    method.__name__ = name
    return method


for _name in ('values', 'items', '__eq__', '__ne__', '__repr__', 'copy', '__reversed__', '__or__', '__ror__',
              '__ior__', 'popitem', 'pop', 'setdefault', 'update', 'clear', '__setitem__', '__delitem__'):
    setattr(LazyTable, _name, _filling(_name))
LazyTable.__hash__ = None  # type: ignore[assignment]
