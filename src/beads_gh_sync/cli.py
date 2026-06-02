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
        return 0
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
    except Exception as e:
        print(f"[beads-gh-sync] {a.command} failed: {e}", file=sys.stderr)
        return 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
