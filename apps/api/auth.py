from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Single-user admin auth via a shared secret.

    The control-plane endpoints (bot CRUD) are mutating and must never be open
    on the public deployment. Behaviour:

    - ``API_KEY`` unset  → the admin API is disabled (503). The static
      dashboard keeps working; only the admin endpoints are gated off.
    - ``API_KEY`` set    → callers must send a matching ``X-API-Key`` header.

    Comparison is constant-time to avoid leaking the key via timing.
    """
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin API disabled: set API_KEY to enable bot management",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-API-Key",
        )
