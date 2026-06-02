from __future__ import annotations
import re
from .models import BeadsIssue

_MARKER = "<!-- beads-id: {id} -->"
_MARKER_RE = re.compile(r"<!-- beads-id: ([a-z0-9-]+) -->")

def project_status(issue: BeadsIssue) -> str:
    if issue.is_closed:
        return "Done"
    if issue.status == "in_progress":
        return "In progress"
    if issue.status == "blocked" or issue.has_open_blockers:
        return "Backlog"
    return "Ready"

def project_priority(issue: BeadsIssue) -> str:
    return {0: "P0", 1: "P1"}.get(issue.priority, "P2")

def type_label(issue: BeadsIssue) -> str:
    return f"type:{issue.issue_type}"

def gh_issue_closed(issue: BeadsIssue) -> bool:
    return issue.is_closed

def with_marker(body: str, beads_id: str) -> str:
    return f"{body}\n\n{_MARKER.format(id=beads_id)}"

def marker_id(body: str) -> str | None:
    m = _MARKER_RE.search(body or "")
    return m.group(1) if m else None
