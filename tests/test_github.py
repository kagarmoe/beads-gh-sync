import json
from beads_gh_sync import github

def test_open_issue_numbers(monkeypatch):
    monkeypatch.setattr(github, "_gh", lambda args: json.dumps(
        [{"number": 1, "title": "a", "state": "OPEN", "body": "x"},
         {"number": 2, "title": "b", "state": "CLOSED", "body": "y"}]))
    items = github.list_issues("kagarmoe", "idle_chapters")
    assert [i.number for i in items] == [1, 2]
    assert items[1].closed is True

def test_create_issue_parses_number(monkeypatch):
    monkeypatch.setattr(github, "_gh",
        lambda args: "https://github.com/kagarmoe/idle_chapters/issues/57\n")
    n = github.create_issue("kagarmoe", "idle_chapters", title="T", body="B", labels=["type:task"])
    assert n == 57

def test_project_field_options_shape(monkeypatch):
    resp = {"data":{"node":{"fields":{"nodes":[
        {"id":"F1","name":"Status","options":[{"id":"o1","name":"Ready"},{"id":"o2","name":"Done"}]},
        {"id":"F2","name":"Title"}]}}}}
    monkeypatch.setattr(github, "_gh", lambda args: json.dumps(resp))
    fo = github.project_field_options("PVT_1")
    assert fo["Status"]["options"]["Done"] == "o2"
    assert "Title" not in fo
