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
