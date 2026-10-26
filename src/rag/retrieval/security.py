"""Document level security trimming.

Each chunk carries the Entra ID groups allowed to read its source document. A query is
filtered to the caller's groups inside the index (OData ``search.in``), and every hit is
checked again in the application before it reaches the prompt. A chunk without groups is
visible to nobody.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from rag.models import Chunk

GROUP_FIELD = "group_ids"
_GROUP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_GROUPS = 200


class InvalidGroupError(ValueError):
    """A group identifier that could break out of the OData filter."""


def normalize_groups(groups: Iterable[str]) -> tuple[str, ...]:
    """Validate and de-duplicate group ids. Rejects anything that is not a plain identifier."""
    cleaned = sorted({g.strip() for g in groups if g and g.strip()})
    for group in cleaned:
        if not _GROUP_ID.fullmatch(group):
            msg = f"invalid group identifier: {group[:40]!r}"
            raise InvalidGroupError(msg)
    if len(cleaned) > MAX_GROUPS:
        msg = f"too many groups ({len(cleaned)} > {MAX_GROUPS}); resolve overage server side"
        raise InvalidGroupError(msg)
    return tuple(cleaned)


def build_security_filter(groups: Iterable[str]) -> str:
    """OData filter that keeps documents sharing at least one group with the caller.

    ``search.in`` with an explicit delimiter is the documented pattern for security trimming
    and stays fast with hundreds of values. With no groups the filter matches nothing.
    """
    normalized = normalize_groups(groups)
    if not normalized:
        return f"{GROUP_FIELD}/any(g: false)"
    joined = ",".join(normalized)
    return f"{GROUP_FIELD}/any(g: search.in(g, '{joined}', ','))"


def is_visible(chunk: Chunk, groups: Iterable[str]) -> bool:
    return bool(chunk.acl_groups) and not set(chunk.acl_groups).isdisjoint(groups)
