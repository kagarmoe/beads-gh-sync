from beads_gh_sync.models import BeadsIssue
from beads_gh_sync import mapping

def mk(status="open", priority=2, itype="task", deps=0):
    return BeadsIssue("id","t","d",status,priority,itype,deps)

def test_status_to_column():
    assert mapping.project_status(mk(status="in_progress")) == "In progress"
    assert mapping.project_status(mk(status="closed")) == "Done"
    assert mapping.project_status(mk(status="open", deps=1)) == "Backlog"
    assert mapping.project_status(mk(status="open", deps=0)) == "Ready"
    assert mapping.project_status(mk(status="blocked")) == "Backlog"

def test_priority_label():
    assert mapping.project_priority(mk(priority=0)) == "P0"
    assert mapping.project_priority(mk(priority=1)) == "P1"
    assert mapping.project_priority(mk(priority=2)) == "P2"
    assert mapping.project_priority(mk(priority=4)) == "P2"

def test_type_label():
    assert mapping.type_label(mk(itype="bug")) == "type:bug"

def test_issue_closed_flag():
    assert mapping.gh_issue_closed(mk(status="closed")) is True
    assert mapping.gh_issue_closed(mk(status="open")) is False

def test_body_marker_roundtrip():
    body = mapping.with_marker("Hello", "chapters-abc")
    assert mapping.marker_id(body) == "chapters-abc"
    assert "Hello" in body
