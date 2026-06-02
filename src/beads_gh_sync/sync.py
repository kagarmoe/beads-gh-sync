from __future__ import annotations
from . import mapping
from .models import BeadsIssue
from .linkmap import LinkMap

# Beads issue types NOT mirrored to GitHub by default. `task` covers granular
# sub-items (e.g. "Task 1: ...") that would clutter the public showcase; beads
# remains the complete record, GitHub shows the meaningful work items.
DEFAULT_SKIP_TYPES = frozenset({"task"})

def push(issues: list[BeadsIssue], lm: LinkMap, gh, *, owner, repo, project_id,
         skip_types: frozenset[str] = DEFAULT_SKIP_TYPES) -> None:
    fopts = gh.project_field_options(project_id)
    for issue in issues:
        if issue.issue_type in skip_types:
            continue  # not mirrored (e.g. granular sub-tasks); stays beads-only
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

def pull(gh_issues, lm: LinkMap, bd, *, repo_path) -> None:
    """Inbox: import GitHub issues with no link into beads. Beads stays canonical for linked ones."""
    for gi in gh_issues:
        if lm.bd_for(gi.number) is not None:
            continue
        new_id = bd.create_issue(repo_path, title=gi.title, description=gi.body,
                                 issue_type="task", priority=2)
        lm.link(new_id, gi.number)
    lm.save()

def reconcile(*, repo_path, owner, repo, project_id, lm, bd, gh) -> None:
    pull(gh.list_issues(owner, repo), lm, bd, repo_path=repo_path)
    push(bd.list_issues(repo_path), lm, gh, owner=owner, repo=repo, project_id=project_id)
