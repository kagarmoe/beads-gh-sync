from __future__ import annotations
import json, re, subprocess
from dataclasses import dataclass

@dataclass(frozen=True)
class GhIssue:
    number: int
    title: str
    body: str
    closed: bool

def _gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout

def list_issues(owner: str, repo: str) -> list[GhIssue]:
    out = _gh(["issue", "list", "-R", f"{owner}/{repo}", "--state", "all",
               "--limit", "1000", "--json", "number,title,body,state"])
    return [GhIssue(i["number"], i["title"], i.get("body") or "",
                    i["state"] == "CLOSED") for i in json.loads(out)]

def create_issue(owner, repo, *, title, body, labels) -> int:
    args = ["issue", "create", "-R", f"{owner}/{repo}", "--title", title, "--body", body]
    for l in labels:
        args += ["--label", l]
    url = _gh(args).strip().splitlines()[-1]
    return int(re.search(r"/issues/(\d+)", url).group(1))

def update_issue(owner, repo, number, *, title, body) -> None:
    _gh(["issue", "edit", str(number), "-R", f"{owner}/{repo}",
         "--title", title, "--body", body])

def set_issue_state(owner, repo, number, *, closed: bool) -> None:
    verb = "close" if closed else "reopen"
    _gh(["issue", verb, str(number), "-R", f"{owner}/{repo}"])

def ensure_label(owner, repo, number, label) -> None:
    _gh(["issue", "edit", str(number), "-R", f"{owner}/{repo}", "--add-label", label])

def ensure_label_exists(owner, repo, label) -> None:
    # A label must exist in the repo before an issue can reference it.
    # `gh label create --force` is idempotent (creates or updates).
    _gh(["label", "create", label, "-R", f"{owner}/{repo}", "--color", "ededed", "--force"])

def _graphql(query: str, **vars) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for k, v in vars.items():
        args += ["-F" if isinstance(v, int) else "-f", f"{k}={v}"]
    return json.loads(_gh(args))

def project_field_options(project_id: str) -> dict[str, dict]:
    """Return {field_name: {"id": fid, "options": {opt_name: opt_id}}} for single-selects."""
    q = """query($p:ID!){ node(id:$p){ ... on ProjectV2 { fields(first:50){ nodes {
      ... on ProjectV2SingleSelectField { id name options { id name } } } } } } }"""
    nodes = _graphql(q, p=project_id)["data"]["node"]["fields"]["nodes"]
    out = {}
    for f in nodes:
        if f and "options" in f:
            out[f["name"]] = {"id": f["id"], "options": {o["name"]: o["id"] for o in f["options"]}}
    return out

def add_issue_to_project(project_id: str, issue_node_id: str) -> str:
    q = """mutation($p:ID!,$c:ID!){ addProjectV2ItemById(input:{projectId:$p,contentId:$c}){ item { id } } }"""
    return _graphql(q, p=project_id, c=issue_node_id)["data"]["addProjectV2ItemById"]["item"]["id"]

def issue_node_id(owner, repo, number) -> str:
    return _gh(["issue", "view", str(number), "-R", f"{owner}/{repo}",
                "--json", "id", "-q", ".id"]).strip()

def set_single_select(project_id, item_id, field_id, option_id) -> None:
    q = """mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){ updateProjectV2ItemFieldValue(input:{
      projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){ projectV2Item{ id } } }"""
    _graphql(q, p=project_id, i=item_id, f=field_id, o=option_id)
