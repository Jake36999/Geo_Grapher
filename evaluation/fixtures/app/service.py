from .helpers import retry_save


def process(value):
    """Validate input before the durable write helper."""
    if value is None:
        return None
    return retry_save(value)
