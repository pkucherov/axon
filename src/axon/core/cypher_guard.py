"""Shared Cypher query safety utilities.

Provides a compiled regex for detecting write keywords in Cypher queries.
Used by both the MCP tools layer and the web API routes to enforce
read-only query execution.
"""

from __future__ import annotations

import re

WRITE_KEYWORDS = re.compile(
    r"\b(DELETE|DROP|CREATE|SET|REMOVE|MERGE|DETACH|INSTALL|LOAD|COPY|CALL)\b",
    re.IGNORECASE,
)
