from __future__ import annotations
from dataclasses import dataclass

CLOSED_STATUSES = {"closed"}

@dataclass(frozen=True)
class BeadsIssue:
    id: str
    title: str
    description: str
    status: str
    priority: int
    issue_type: str
    dependency_count: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "BeadsIssue":
        return cls(
            id=d["id"],
            title=d.get("title", ""),
            description=d.get("description", "") or "",
            status=d.get("status", "open"),
            priority=int(d.get("priority", 2)),
            issue_type=d.get("issue_type", "task"),
            dependency_count=int(d.get("dependency_count", 0)),
        )

    @property
    def is_closed(self) -> bool:
        return self.status in CLOSED_STATUSES

    @property
    def has_open_blockers(self) -> bool:
        return self.dependency_count > 0
