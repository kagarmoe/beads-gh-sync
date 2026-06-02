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
    assert c.for_repo("/x/other") is None
