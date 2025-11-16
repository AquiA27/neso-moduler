# Ensure kasa overrides are applied at import time
try:
    from . import kasa_override  # noqa: F401
except Exception:
    # Fail silently; base behavior continues
    pass
