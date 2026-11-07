"""Locate authoritative bundled resources in an editable checkout or wheel."""
from pathlib import Path
import sys

def resource_root():
    checkout=Path(__file__).resolve().parents[2]
    if (checkout/'contracts/geographer.schema.sql').is_file():return checkout
    installed=Path(sys.prefix)/'share/geographer'
    if (installed/'contracts/geographer.schema.sql').is_file():return installed
    raise RuntimeError('Geo Grapher resources missing; install the complete wheel or use the project checkout')
