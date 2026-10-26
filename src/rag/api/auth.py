"""Resolve the caller's identity and groups.

In Azure the service runs behind built-in authentication (Container Apps or App Service),
which validates the Entra ID token and forwards the claims in ``X-MS-CLIENT-PRINCIPAL``.
The header is only trustworthy because ingress is restricted to that front door; the
``dev-headers`` mode exists for local runs and must never be enabled in a deployment.
"""

from __future__ import annotations

import base64
import binascii
import json

from fastapi import HTTPException, Request, status

from rag.models import Principal
from rag.retrieval.security import InvalidGroupError, normalize_groups

PRINCIPAL_HEADER = "x-ms-client-principal"
GROUP_CLAIMS = frozenset(
    {"groups", "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"}
)
OID_CLAIMS = frozenset({"oid", "http://schemas.microsoft.com/identity/claims/objectidentifier"})


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def principal_from_easy_auth(header: str | None) -> Principal:
    if not header:
        raise _unauthorized("missing client principal")
    try:
        payload = json.loads(base64.b64decode(header, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise _unauthorized("malformed client principal") from exc
    claims = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(claims, list):
        raise _unauthorized("client principal has no claims")
    user_id = ""
    groups: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        typ, val = str(claim.get("typ", "")), str(claim.get("val", ""))
        if typ in OID_CLAIMS:
            user_id = val
        elif typ in GROUP_CLAIMS:
            groups.append(val)
        elif typ == "_claim_names" and "groups" in val:
            # Group overage: the token holds a pointer to Graph instead of the groups.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="group overage: resolve groups server side or use app roles",
            )
    if not user_id:
        raise _unauthorized("client principal has no object id")
    try:
        return Principal(user_id=user_id, groups=normalize_groups(groups))
    except InvalidGroupError as exc:
        raise _unauthorized("invalid group claim") from exc


def principal_from_dev_headers(request: Request) -> Principal:
    user_id = request.headers.get("x-user-id", "")
    if not user_id:
        raise _unauthorized("missing x-user-id")
    raw = request.headers.get("x-user-groups", "")
    try:
        return Principal(user_id=user_id, groups=normalize_groups(raw.split(",")))
    except InvalidGroupError as exc:
        raise _unauthorized("invalid group") from exc


def resolve_principal(request: Request, mode: str) -> Principal:
    if mode == "dev-headers":
        return principal_from_dev_headers(request)
    return principal_from_easy_auth(request.headers.get(PRINCIPAL_HEADER))
