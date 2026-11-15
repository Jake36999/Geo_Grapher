"""Read published snapshots without running store schema/migration writes."""
from pathlib import Path
import sqlite3
from geographer.store import SnapshotStore

class ReadOnlyStore(SnapshotStore):
    def __init__(self,path):
        self._columns={}
        self.connection=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
        self.connection.row_factory=sqlite3.Row
        self.connection.execute('PRAGMA query_only=ON')

class FrozenGraphs:
    def __init__(self,catalog):
        self.catalog=sqlite3.connect(Path(catalog).resolve().as_uri()+'?mode=ro',uri=True)
        self.catalog.row_factory=sqlite3.Row;self.graphs={};self.stores={};self.snapshots={}
    def graph(self,label):
        if label not in self.graphs:
            row=self.catalog.execute('SELECT * FROM graphs WHERE label=?',(label,)).fetchone()
            if row is None or not row['code_database']:raise ValueError('Frozen code graph unavailable')
            store=ReadOnlyStore(row['code_database']);self.stores[label]=store
            self.graphs[label]=store.graph(row['snapshot_id']);self.snapshots[label]=row['snapshot_id']
        return self.graphs[label]
    def close(self):
        for store in self.stores.values():store.close()
        self.catalog.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
