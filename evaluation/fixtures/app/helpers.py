from .storage import save


def retry_save(value):
    """Retry the durable write once after an OSError."""
    try:
        return save(value)
    except OSError:
        return save(value)
