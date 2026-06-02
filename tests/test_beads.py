import json
from beads_gh_sync import beads
from beads_gh_sync.models import BeadsIssue

def test_list_issues_parses(monkeypatch):
    payload = json.dumps([{"id":"chapters-abc","title":"T","description":"D",
        "status":"open","priority":2,"issue_type":"task","dependency_count":0}])
    monkeypatch.setattr(beads, "_run", lambda args, cwd: payload)
    issues = beads.list_issues("/x/idle_chapters")
    assert isinstance(issues[0], BeadsIssue) and issues[0].id == "chapters-abc"

def test_create_issue_returns_id(monkeypatch):
    monkeypatch.setattr(beads, "_run", lambda args, cwd: "chapters-new\n")
    new_id = beads.create_issue("/x/idle_chapters", title="New", description="b",
                                issue_type="task", priority=2)
    assert new_id == "chapters-new"
