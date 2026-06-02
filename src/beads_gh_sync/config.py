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
