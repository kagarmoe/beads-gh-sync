from beads_gh_sync import sync
from beads_gh_sync.models import BeadsIssue
from beads_gh_sync.linkmap import LinkMap

class FakeGH:
    def __init__(self): self.created=[]; self.updated=[]
    def create_issue(self, o,r,*,title,body,labels): self.created.append(title); return 100+len(self.created)
    def update_issue(self, o,r,n,*,title,body): self.updated.append(n)
    def set_issue_state(self, o,r,n,*,closed): pass
    def ensure_label(self,o,r,n,label): pass
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
    assert gh.created == ["A"]
    assert 7 in gh.updated
    assert lm.gh_for("chapters-a") == 101

from beads_gh_sync.github import GhIssue

class FakeBeads:
    def __init__(self): self.created=[]
    def create_issue(self, path,*,title,description,issue_type,priority):
        self.created.append(title); return f"chapters-new{len(self.created)}"

def test_pull_imports_only_unlinked_github(tmp_path):
    gh_issues = [GhIssue(1,"Existing","b",False), GhIssue(2,"Solo idea","b2",False)]
    lm = LinkMap.load(tmp_path/"m.json"); lm.link("chapters-x", 1)
    bd = FakeBeads()
    sync.pull(gh_issues, lm, bd, repo_path="/x")
    assert bd.created == ["Solo idea"]
    assert lm.bd_for(2) == "chapters-new1"
