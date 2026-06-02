from __future__ import annotations
import json, subprocess
from .models import BeadsIssue

def _run(args: list[str], cwd: str) -> str:
    return subprocess.run(["bd", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout

def list_issues(repo_path: str) -> list[BeadsIssue]:
    out = _run(["list", "--json", "--status=all"], repo_path)
    data = json.loads(out)
    rows = data if isinstance(data, list) else data.get("issues", [])
    return [BeadsIssue.from_dict(r) for r in rows]

def create_issue(repo_path, *, title, description, issue_type, priority) -> str:
    out = _run(["q", "--title", title, "--description", description,
                "--type", issue_type, "--priority", str(priority)], repo_path)
    return out.strip().splitlines()[-1].strip()

def set_status(repo_path, beads_id, status) -> None:
    _run(["update", beads_id, "--status", status], repo_path)
