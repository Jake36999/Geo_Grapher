from .service import process
from .storage import save


def submit(value):
    """Submit through the service boundary."""
    return process(value)


def bypass(value):
    """Legacy bypass retained to exercise architecture checks."""
    return save(value)
