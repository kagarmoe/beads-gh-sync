# Beads ↔ GitHub Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A shared Python CLI that mirrors beads issues to GitHub Issues + Projects v2 (push), imports GitHub-created issues into beads (pull), and unions existing backlogs (reconcile) — wired to SessionStart (pull) and pre-push (push) hooks.

**Architecture:** beads is canonical; GitHub is mirror + inbox. Pure-function core (models, field mapping, link map) wrapped by two thin adapters that shell out to `bd --json` and `gh` (+ `gh api graphql` for Projects v2). A versioned `.beads/gh-sync-map.json` per repo links `beads-id ↔ gh-issue-number` for idempotency. Repos opt in via a central `config.json`.

**Tech Stack:** Python 3.12 (stdlib only — `subprocess`, `json`, `dataclasses`, `argparse`), `pytest`, the `bd` and `gh` CLIs.

See the design: `docs/plans/2026-06-02-beads-gh-sync-design.md`.

---

## File Structure

```
beads-gh-sync/
  pyproject.toml                     # package + pytest config
  config.json                        # enrolled repos -> project (repo_path, project_id, project_number)
  src/beads_gh_sync/
    __init__.py
    models.py        # BeadsIssue dataclass + bd-JSON parsing; status/priority constants
    mapping.py       # pure mappers: status->column, priority->P-label, type->label, body marker
    linkmap.py       # load/save .beads/gh-sync-map.json; lookups; link()
    config.py        # load config.json; resolve a repo path -> ProjectConfig
    beads.py         # adapter: list_issues(), create_issue() via `bd`
    github.py        # adapter: issues (create/update/close/label) + Projects v2 (graphql)
    sync.py          # push(), pull(), reconcile() orchestration
    cli.py           # argparse: push | pull | reconcile | enroll
  hooks/
    pre-push                         # git pre-push hook (warn-only push)
    install.sh                       # install pre-push into a repo; print SessionStart hook JSON
  tests/
    fixtures/bd_issue.json
    test_models.py  test_mapping.py  test_linkmap.py  test_config.py
    test_beads.py   test_github.py   test_sync.py
```

Design boundaries: `models`/`mapping`/`linkmap`/`config` are **pure** (no I/O) → trivially testable. `beads`/`github` are the **only** modules that shell out. `sync` orchestrates; `cli` is the entrypoint.

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `src/beads_gh_sync/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "beads-gh-sync"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create empty package files**

```bash
mkdir -p src/beads_gh_sync tests/fixtures
touch src/beads_gh_sync/__init__.py tests/__init__.py
```

- [ ] **Step 3: Verify pytest runs (no tests yet)**

Run: `python3 -m pytest -q`
Expected: `no tests ran` (exit 5) — confirms pytest + pythonpath work.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src tests
git commit -m "chore: python project scaffold"
```

---

## Task 2: Models (`models.py`)

**Files:** Create `src/beads_gh_sync/models.py`, `tests/test_models.py`, `tests/fixtures/bd_issue.json`

- [ ] **Step 1: Write fixture** `tests/fixtures/bd_issue.json`

```json
{"id":"chapters-abc","title":"Add time mechanics","description":"Body text","status":"in_progress","priority":1,"issue_type":"feature","assignee":"","owner":"Kimberly Garmoe","created_at":"2026-05-01T00:00:00Z","updated_at":"2026-05-02T00:00:00Z","dependency_count":2,"dependent_count":0,"comment_count":0}
```

- [ ] **Step 2: Write the failing test** `tests/test_models.py`

```python
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
    assert issue.has_open_blockers is True   # dependency_count > 0

def test_is_closed():
    data = json.loads(FIX.read_text()); data["status"] = "closed"
    assert BeadsIssue.from_dict(data).is_closed is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: beads_gh_sync.models`).

- [ ] **Step 4: Implement `src/beads_gh_sync/models.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_models.py -v` → Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/beads_gh_sync/models.py tests/test_models.py tests/fixtures/bd_issue.json
git commit -m "feat: BeadsIssue model + bd-JSON parsing"
```

---

## Task 3: Field mapping (`mapping.py`)

**Files:** Create `src/beads_gh_sync/mapping.py`, `tests/test_mapping.py`

- [ ] **Step 1: Write the failing test** `tests/test_mapping.py`

```python
from beads_gh_sync.models import BeadsIssue
from beads_gh_sync import mapping

def mk(status="open", priority=2, itype="task", deps=0):
    return BeadsIssue("id","t","d",status,priority,itype,deps)

def test_status_to_column():
    assert mapping.project_status(mk(status="in_progress")) == "In progress"
    assert mapping.project_status(mk(status="closed")) == "Done"
    assert mapping.project_status(mk(status="open", deps=1)) == "Backlog"   # blocked-by-deps
    assert mapping.project_status(mk(status="open", deps=0)) == "Ready"     # ready
    assert mapping.project_status(mk(status="blocked")) == "Backlog"

def test_priority_label():
    assert mapping.project_priority(mk(priority=0)) == "P0"
    assert mapping.project_priority(mk(priority=1)) == "P1"
    assert mapping.project_priority(mk(priority=2)) == "P2"
    assert mapping.project_priority(mk(priority=4)) == "P2"   # collapse 2-4 -> P2

def test_type_label():
    assert mapping.type_label(mk(itype="bug")) == "type:bug"

def test_issue_closed_flag():
    assert mapping.gh_issue_closed(mk(status="closed")) is True
    assert mapping.gh_issue_closed(mk(status="open")) is False

def test_body_marker_roundtrip():
    body = mapping.with_marker("Hello", "chapters-abc")
    assert mapping.marker_id(body) == "chapters-abc"
    assert "Hello" in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_mapping.py -v` → Expected: FAIL (no module).

- [ ] **Step 3: Implement `src/beads_gh_sync/mapping.py`**

```python
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
    return "Ready"  # open, unblocked

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
```

- [ ] **Step 4: Run to verify it passes** → `python3 -m pytest tests/test_mapping.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/beads_gh_sync/mapping.py tests/test_mapping.py
git commit -m "feat: beads->github field/status/priority mapping"
```

---

## Task 4: Link map (`linkmap.py`)

**Files:** Create `src/beads_gh_sync/linkmap.py`, `tests/test_linkmap.py`

- [ ] **Step 1: Write the failing test** `tests/test_linkmap.py`

```python
from beads_gh_sync.linkmap import LinkMap

def test_link_and_lookup(tmp_path):
    p = tmp_path / "gh-sync-map.json"
    lm = LinkMap.load(p)
    assert lm.gh_for("chapters-abc") is None
    lm.link("chapters-abc", 42)
    assert lm.gh_for("chapters-abc") == 42
    assert lm.bd_for(42) == "chapters-abc"
    lm.save()
    assert LinkMap.load(p).gh_for("chapters-abc") == 42   # persisted

def test_unlinked_github_numbers(tmp_path):
    lm = LinkMap.load(tmp_path / "m.json")
    lm.link("chapters-abc", 42)
    assert lm.unlinked([42, 43, 44]) == [43, 44]
```

- [ ] **Step 2: Run to verify it fails** → FAIL (no module).

- [ ] **Step 3: Implement `src/beads_gh_sync/linkmap.py`**

```python
from __future__ import annotations
import json, pathlib

class LinkMap:
    def __init__(self, path: pathlib.Path, bd_to_gh: dict[str, int]):
        self._path = path
        self._bd_to_gh = bd_to_gh
        self._gh_to_bd = {v: k for k, v in bd_to_gh.items()}

    @classmethod
    def load(cls, path) -> "LinkMap":
        path = pathlib.Path(path)
        data = json.loads(path.read_text()) if path.exists() else {}
        # stored as {"beads_id": gh_number}
        return cls(path, {k: int(v) for k, v in data.items()})

    def gh_for(self, beads_id: str) -> int | None:
        return self._bd_to_gh.get(beads_id)

    def bd_for(self, gh_number: int) -> str | None:
        return self._gh_to_bd.get(gh_number)

    def link(self, beads_id: str, gh_number: int) -> None:
        self._bd_to_gh[beads_id] = gh_number
        self._gh_to_bd[gh_number] = beads_id

    def unlinked(self, gh_numbers: list[int]) -> list[int]:
        return [n for n in gh_numbers if n not in self._gh_to_bd]

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._bd_to_gh, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run to verify it passes** → PASS.

- [ ] **Step 5: Commit** → `git commit -m "feat: versioned beads<->github link map"`

---

## Task 5: Config (`config.py`)

**Files:** Create `src/beads_gh_sync/config.py`, `config.json`, `tests/test_config.py`

- [ ] **Step 1: Write the failing test** `tests/test_config.py`

```python
import json
from beads_gh_sync.config import Config, ProjectConfig

def test_resolve_known_repo(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"repos": [
        {"repo_path": "/x/idle_chapters", "owner": "kagarmoe",
         "repo": "idle_chapters", "project_number": 1, "project_id": "PVT_1"}]}))
    c = Config.load(cfg)
    pc = c.for_repo("/x/idle_chapters")
    assert pc.project_number == 1 and pc.repo == "idle_chapters"
    assert c.for_repo("/x/other") is None   # unenrolled -> no-op
```

- [ ] **Step 2: Run to verify it fails** → FAIL.

- [ ] **Step 3: Implement `src/beads_gh_sync/config.py`**

```python
from __future__ import annotations
import json, pathlib
from dataclasses import dataclass

@dataclass(frozen=True)
class ProjectConfig:
    repo_path: str
    owner: str
    repo: str
    project_number: int
    project_id: str

class Config:
    def __init__(self, projects: list[ProjectConfig]):
        self._by_path = {pathlib.Path(p.repo_path).resolve().as_posix(): p for p in projects}

    @classmethod
    def load(cls, path) -> "Config":
        data = json.loads(pathlib.Path(path).read_text())
        return cls([ProjectConfig(**r) for r in data.get("repos", [])])

    def for_repo(self, repo_path) -> ProjectConfig | None:
        return self._by_path.get(pathlib.Path(repo_path).resolve().as_posix())
```

- [ ] **Step 4: Create the real `config.json`** (enrolled repos)

```json
{
  "repos": [
    {"repo_path": "/Users/kimberlygarmoe/repos/idle_chapters", "owner": "kagarmoe",
     "repo": "idle_chapters", "project_number": 1, "project_id": "PVT_kwHOAEMkF84BMEZb"},
    {"repo_path": "/Users/kimberlygarmoe/repos/purseinator-app", "owner": "kagarmoe",
     "repo": "purseinator-app", "project_number": 2, "project_id": "PVT_kwHOAEMkF84BZbyk"}
  ]
}
```

- [ ] **Step 5: Run to verify it passes** → PASS.

- [ ] **Step 6: Commit** → `git commit -m "feat: repo->project config"`

---

## Task 6: Beads adapter (`beads.py`)

**Files:** Create `src/beads_gh_sync/beads.py`, `tests/test_beads.py`

- [ ] **Step 1: Write the failing test** `tests/test_beads.py`

```python
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
```

- [ ] **Step 2: Run to verify it fails** → FAIL.

- [ ] **Step 3: Implement `src/beads_gh_sync/beads.py`**

```python
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
    # `bd q` quick-capture prints only the new id
    out = _run(["q", "--title", title, "--description", description,
                "--type", issue_type, "--priority", str(priority)], repo_path)
    return out.strip().splitlines()[-1].strip()

def set_status(repo_path, beads_id, status) -> None:
    _run(["update", beads_id, "--status", status], repo_path)
```

- [ ] **Step 4: Run to verify it passes** → PASS.

- [ ] **Step 5: Manual smoke check** (real `bd`)

Run: `cd ~/repos/idle_chapters && python3 -c "from beads_gh_sync import beads; print(len(beads.list_issues('.')))"` (with `PYTHONPATH=.../src`)
Expected: prints the issue count (e.g. `18`). Confirms the real `bd --json` shape matches.

- [ ] **Step 6: Commit** → `git commit -m "feat: beads adapter (list/create/status)"`

---

## Task 7: GitHub adapter (`github.py`)

**Files:** Create `src/beads_gh_sync/github.py`, `tests/test_github.py`

GitHub Issues use `gh issue ...`; Projects v2 fields require `gh api graphql`. Field/option IDs are
**resolved at runtime by name** (never hardcoded) so the tool survives board edits.

- [ ] **Step 1: Write the failing test** `tests/test_github.py`

```python
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
```

- [ ] **Step 2: Run to verify it fails** → FAIL.

- [ ] **Step 3: Implement `src/beads_gh_sync/github.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes** → PASS.

- [ ] **Step 5: Add Projects v2 helpers (GraphQL) to `github.py`**

```python
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
```

- [ ] **Step 6: Test the GraphQL var-encoding helper** (append to `tests/test_github.py`)

```python
def test_project_field_options_shape(monkeypatch):
    resp = {"data":{"node":{"fields":{"nodes":[
        {"id":"F1","name":"Status","options":[{"id":"o1","name":"Ready"},{"id":"o2","name":"Done"}]},
        {"id":"F2","name":"Title"}]}}}}
    monkeypatch.setattr(github, "_gh", lambda args: json.dumps(resp))
    fo = github.project_field_options("PVT_1")
    assert fo["Status"]["options"]["Done"] == "o2"
    assert "Title" not in fo   # non-single-select excluded
```

Run: `python3 -m pytest tests/test_github.py -v` → PASS.

- [ ] **Step 7: Commit** → `git commit -m "feat: github adapter (issues + Projects v2 graphql)"`

---

## Task 8: Push orchestration (`sync.py` — push)

**Files:** Create `src/beads_gh_sync/sync.py`, `tests/test_sync.py`

- [ ] **Step 1: Write the failing test** `tests/test_sync.py`

```python
from beads_gh_sync import sync
from beads_gh_sync.models import BeadsIssue
from beads_gh_sync.linkmap import LinkMap

class FakeGH:
    def __init__(self): self.created=[]; self.updated=[]; self.fields=[]
    def create_issue(self, o,r,*,title,body,labels): self.created.append(title); return 100+len(self.created)
    def update_issue(self, o,r,n,*,title,body): self.updated.append(n)
    def set_issue_state(self, o,r,n,*,closed): pass
    def ensure_label(self,o,r,n,label): pass
    # project helpers no-op for this test
    def issue_node_id(self,o,r,n): return f"NODE{n}"
    def add_issue_to_project(self,p,c): return "ITEM"
    def project_field_options(self,p): return {"Status":{"id":"S","options":{"Ready":"r","In progress":"ip","Done":"d","Backlog":"b"}},"Priority":{"id":"P","options":{"P0":"0","P1":"1","P2":"2"}}}
    def set_single_select(self,*a,**k): pass

def test_push_creates_unlinked_and_updates_linked(tmp_path):
    issues = [BeadsIssue("chapters-a","A","d","open",2,"task",0),
              BeadsIssue("chapters-b","B","d","closed",1,"bug",0)]
    lm = LinkMap.load(tmp_path/"m.json"); lm.link("chapters-b", 7)
    gh = FakeGH()
    sync.push(issues, lm, gh, owner="o", repo="r", project_id="P")
    assert gh.created == ["A"]          # chapters-a was unlinked -> created
    assert 7 in gh.updated              # chapters-b was linked -> updated
    assert lm.gh_for("chapters-a") == 101   # new link recorded
```

- [ ] **Step 2: Run to verify it fails** → FAIL.

- [ ] **Step 3: Implement `push()` in `src/beads_gh_sync/sync.py`**

```python
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
        # project board: add + set Status/Priority
        item = gh.add_issue_to_project(project_id, gh.issue_node_id(owner, repo, number))
        _set(gh, project_id, item, fopts, "Status", mapping.project_status(issue))
        _set(gh, project_id, item, fopts, "Priority", mapping.project_priority(issue))
    lm.save()

def _set(gh, project_id, item, fopts, field, option_name):
    f = fopts.get(field)
    if not f or option_name not in f["options"]:
        return
    gh.set_single_select(project_id, item, f["id"], f["options"][option_name])
```

- [ ] **Step 4: Run to verify it passes** → PASS.

- [ ] **Step 5: Commit** → `git commit -m "feat: push (beads -> github issues + project)"`

---

## Task 9: Pull orchestration (`sync.py` — pull)

**Files:** Modify `src/beads_gh_sync/sync.py`, `tests/test_sync.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_sync.py`)

```python
from beads_gh_sync.github import GhIssue

class FakeBeads:
    def __init__(self): self.created=[]
    def create_issue(self, path,*,title,description,issue_type,priority):
        self.created.append(title); return f"chapters-new{len(self.created)}"

def test_pull_imports_only_unlinked_github(tmp_path, monkeypatch):
    gh_issues = [GhIssue(1,"Existing","b",False), GhIssue(2,"Solo idea","b2",False)]
    lm = LinkMap.load(tmp_path/"m.json"); lm.link("chapters-x", 1)   # #1 already linked
    bd = FakeBeads()
    sync.pull(gh_issues, lm, bd, repo_path="/x")
    assert bd.created == ["Solo idea"]            # only the unlinked #2 imported
    assert lm.bd_for(2) == "chapters-new1"        # new link recorded
```

- [ ] **Step 2: Run to verify it fails** → FAIL.

- [ ] **Step 3: Implement `pull()` in `sync.py`**

```python
def pull(gh_issues, lm: LinkMap, bd, *, repo_path) -> None:
    """Inbox: import GitHub issues with no link into beads. Beads stays canonical for linked ones."""
    for gi in gh_issues:
        if lm.bd_for(gi.number) is not None:
            continue  # already linked -> beads owns it; don't overwrite
        new_id = bd.create_issue(repo_path, title=gi.title, description=gi.body,
                                 issue_type="task", priority=2)
        lm.link(new_id, gi.number)
    lm.save()
```

- [ ] **Step 4: Run to verify it passes** → PASS.

- [ ] **Step 5: Commit** → `git commit -m "feat: pull (github inbox -> beads)"`

---

## Task 10: Reconcile + CLI (`sync.py`, `cli.py`)

**Files:** Modify `src/beads_gh_sync/sync.py`; create `src/beads_gh_sync/cli.py`

- [ ] **Step 1: Add `reconcile()` to `sync.py`** (union = pull then push)

```python
def reconcile(*, repo_path, owner, repo, project_id, lm, bd, gh) -> None:
    pull(gh.list_issues(owner, repo), lm, bd, repo_path=repo_path)   # import GitHub-only -> beads
    push(bd.list_issues(repo_path), lm, gh, owner=owner, repo=repo, project_id=project_id)  # mirror all -> github
```

- [ ] **Step 2: Write the CLI** `src/beads_gh_sync/cli.py`

```python
from __future__ import annotations
import argparse, pathlib, sys
from . import beads, github, sync
from .config import Config
from .linkmap import LinkMap

CONFIG = pathlib.Path(__file__).resolve().parents[2] / "config.json"

def _ctx(repo_path):
    cfg = Config.load(CONFIG).for_repo(repo_path)
    if cfg is None:
        print(f"[beads-gh-sync] {repo_path} not enrolled; skipping.", file=sys.stderr)
        return None
    lm = LinkMap.load(pathlib.Path(repo_path) / ".beads" / "gh-sync-map.json")
    return cfg, lm

def main(argv=None):
    ap = argparse.ArgumentParser(prog="beads-gh-sync")
    ap.add_argument("command", choices=["push", "pull", "reconcile"])
    ap.add_argument("--repo", default=".", help="repo path (default: cwd)")
    a = ap.parse_args(argv)
    repo_path = str(pathlib.Path(a.repo).resolve())
    ctx = _ctx(repo_path)
    if ctx is None:
        return 0  # no-op for unenrolled repos
    cfg, lm = ctx
    try:
        if a.command == "push":
            sync.push(beads.list_issues(repo_path), lm, github,
                      owner=cfg.owner, repo=cfg.repo, project_id=cfg.project_id)
        elif a.command == "pull":
            sync.pull(github.list_issues(cfg.owner, cfg.repo), lm, beads, repo_path=repo_path)
        else:
            sync.reconcile(repo_path=repo_path, owner=cfg.owner, repo=cfg.repo,
                           project_id=cfg.project_id, lm=lm, bd=beads, gh=github)
    except Exception as e:                      # warn-only: never block caller
        print(f"[beads-gh-sync] {a.command} failed: {e}", file=sys.stderr)
        return 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Test CLI no-ops on unenrolled repo + warn-only**

(append to `tests/test_sync.py`)

```python
from beads_gh_sync import cli
def test_cli_noop_unenrolled(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "CONFIG", tmp_path/"config.json")
    (tmp_path/"config.json").write_text('{"repos":[]}')
    assert cli.main(["push", "--repo", str(tmp_path)]) == 0
    assert "not enrolled" in capsys.readouterr().err
```

Run: `python3 -m pytest tests/test_sync.py -v` → PASS.

- [ ] **Step 4: Commit** → `git commit -m "feat: reconcile + warn-only CLI (push/pull/reconcile)"`

---

## Task 11: Hooks + first reconciliation

**Files:** Create `hooks/pre-push`, `hooks/install.sh`

- [ ] **Step 1: Write `hooks/pre-push`** (warn-only; never blocks the push)

```bash
#!/usr/bin/env bash
# beads-gh-sync pre-push: mirror beads -> GitHub. Never blocks the push.
python3 -m beads_gh_sync.cli push --repo "$(git rev-parse --show-toplevel)" \
  || echo "[beads-gh-sync] push hook error (ignored)" >&2
exit 0
```

- [ ] **Step 2: Write `hooks/install.sh`** (install pre-push into a repo; print SessionStart JSON)

```bash
#!/usr/bin/env bash
set -euo pipefail
TOOL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:?usage: install.sh <repo-path>}"
ln -sf "$TOOL_DIR/hooks/pre-push" "$REPO/.git/hooks/pre-push"
chmod +x "$TOOL_DIR/hooks/pre-push"
echo "Installed pre-push hook in $REPO"
cat <<EOF

Add this to ~/.claude/settings.json "hooks"."SessionStart" to enable PULL on session start:
  { "type": "command",
    "command": "cd $TOOL_DIR && PYTHONPATH=src python3 -m beads_gh_sync.cli pull --repo \\"\\$(pwd)\\"" }
EOF
```

- [ ] **Step 3: Make executable + commit**

```bash
chmod +x hooks/pre-push hooks/install.sh
git add hooks && git commit -m "feat: pre-push hook + installer; SessionStart snippet"
```

- [ ] **Step 4: First reconciliation (manual, idle_chapters) — the union**

```bash
cd ~/repos/beads-gh-sync
PYTHONPATH=src python3 -m beads_gh_sync.cli reconcile --repo ~/repos/idle_chapters
```
Expected: imports the ~18 GitHub-only issues into beads, pushes all beads issues to GitHub + the
Project board, writes `~/repos/idle_chapters/.beads/gh-sync-map.json` with an entry per issue.

- [ ] **Step 5: Verify idempotency**

```bash
gh issue list -R kagarmoe/idle_chapters --state all --json number -q "length"   # note count
PYTHONPATH=src python3 -m beads_gh_sync.cli reconcile --repo ~/repos/idle_chapters
gh issue list -R kagarmoe/idle_chapters --state all --json number -q "length"   # MUST be unchanged
```
Expected: second run creates **zero** new issues (map prevents duplicates).

- [ ] **Step 6: Commit the map + repeat for purseinator-app**

```bash
cd ~/repos/idle_chapters && git add .beads/gh-sync-map.json && git commit -m "chore: beads<->gh sync map"
cd ~/repos/beads-gh-sync && PYTHONPATH=src python3 -m beads_gh_sync.cli reconcile --repo ~/repos/purseinator-app
```

---

## Verification (end-to-end, from the spec)

1. **Reconcile** idle_chapters → beads grows to the union (~36), Project shows all items, map has an entry per issue.
2. **Idempotency** → re-run reconcile creates 0 new issues (Task 11 Step 5).
3. **Pull** → open a new GitHub issue, run `cli pull --repo ~/repos/idle_chapters`, confirm it appears in `bd list` with a map entry.
4. **Push** → create a beads issue, `git push`, confirm it lands as a GitHub issue on the board with correct Status/Priority/`type:` label.
5. **Failure mode** → with networking off, `git push` still succeeds (pre-push prints a warning, `exit 0`).
6. Repeat 1–5 for purseinator-app (Project #2).

## Self-Review notes
- **Spec coverage:** model A (pull doesn't overwrite linked beads — Task 9); union reconcile (Task 10); map-file idempotency (Tasks 4, 11.5); status/priority/type/closed mapping (Task 3); warn-only (Task 10 CLI + Task 11 hook); config no-op for unenrolled (Task 5, Task 10.3). Deferred deps/comments: not implemented (intentional).
- **Enrollment** (spec §Enrollment): the `enroll` flow (create/link Project + add config entry) is **not** in this plan — it's an interactive, policy-driven action; tracked as follow-up, not v1 automation. `config.json` is hand-seeded for the two known repos (Task 5).
- **Naming consistency:** `_gh`/`_run`/`_graphql` adapters; `gh_for`/`bd_for`/`unlinked`/`link`/`save` on LinkMap; `project_status`/`project_priority`/`type_label`/`gh_issue_closed`/`with_marker`/`marker_id` in mapping — all referenced consistently across tasks.
