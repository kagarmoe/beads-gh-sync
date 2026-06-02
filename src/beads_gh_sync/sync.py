from __future__ import annotations
from . import mapping
from .models import BeadsIssue
from .linkmap import LinkMap

def push(issues: list[BeadsIssue], lm: LinkMap, gh, *, owner, repo, project_id) -> None:
    fopts = gh.project_field_options(project_id)
    for issue in issues:
        body = mapping.with_marker(issue.description, issue.id)
        labels = [mapping.type_label(issue)]
        number = lm.gh_for(issue.id)
        if number is None:
            number = gh.create_issue(owner, repo, title=issue.title, body=body, labels=labels)
            lm.link(issue.id, number)
        else:
            gh.update_issue(owner, repo, number, title=issue.title, body=body)
            gh.ensure_label(owner, repo, number, labels[0])
        gh.set_issue_state(owner, repo, number, closed=mapping.gh_issue_closed(issue))
        item = gh.add_issue_to_project(project_id, gh.issue_node_id(owner, repo, number))
        _set(gh, project_id, item, fopts, "Status", mapping.project_status(issue))
        _set(gh, project_id, item, fopts, "Priority", mapping.project_priority(issue))
    lm.save()

def _set(gh, project_id, item, fopts, field, option_name):
    f = fopts.get(field)
    if not f or option_name not in f["options"]:
        return
    gh.set_single_select(project_id, item, f["id"], f["options"][option_name])
