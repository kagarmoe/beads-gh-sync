from beads_gh_sync.linkmap import LinkMap

def test_link_and_lookup(tmp_path):
    p = tmp_path / "gh-sync-map.json"
    lm = LinkMap.load(p)
    assert lm.gh_for("chapters-abc") is None
    lm.link("chapters-abc", 42)
    assert lm.gh_for("chapters-abc") == 42
    assert lm.bd_for(42) == "chapters-abc"
    lm.save()
    assert LinkMap.load(p).gh_for("chapters-abc") == 42

def test_unlinked_github_numbers(tmp_path):
    lm = LinkMap.load(tmp_path / "m.json")
    lm.link("chapters-abc", 42)
    assert lm.unlinked([42, 43, 44]) == [43, 44]
