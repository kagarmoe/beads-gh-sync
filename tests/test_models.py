import json, pathlib
from beads_gh_sync.models import BeadsIssue

FIX = pathlib.Path(__file__).parent / "fixtures" / "bd_issue.json"

def test_from_json_parses_core_fields():
    issue = BeadsIssue.from_dict(json.loads(FIX.read_text()))
    assert issue.id == "chapters-abc"
    assert issue.title == "Add time mechanics"
    assert issue.status == "in_progress"
    assert issue.priority == 1
    assert issue.issue_type == "feature"
    assert issue.has_open_blockers is True

def test_is_closed():
    data = json.loads(FIX.read_text()); data["status"] = "closed"
    assert BeadsIssue.from_dict(data).is_closed is True
