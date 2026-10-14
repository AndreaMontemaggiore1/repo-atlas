"""Tests for locate.py on the fixture repo from test_scripts.

The ripgrep test runs if `rg` is on PATH or RG_PATH points to an rg binary; otherwise skipped.
"""
import os, shutil

import pytest

from test_scripts import SCRIPTS, move_functions, repo, script, true_range, write, CORE_V2  # noqa: F401
import locate  # noqa: E402  (SCRIPTS is on sys.path via test_scripts)

RG = os.environ.get("RG_PATH") or shutil.which("rg")


@pytest.fixture
def no_rg(monkeypatch):
    monkeypatch.setattr(locate.shutil, "which", lambda name: None)


def top(root, q, k=5):
    return [(f, n, s, e, src) for _, f, n, s, e, src, _ in locate.locate(root, q, k)[1]]


def test_tokens_split_and_stem():
    t = locate.tokens("getHTTPResponse snake_case_name redirects")
    assert {"get", "http", "respons", "gethttpresponse", "snak", "case", "name", "snakecasename",
            "redirect"} <= set(t), t  # stems keep >= 4 chars: case/name untouched
    assert locate.query_terms("where is the code I would change to: fix the redirects") == ["redirect"]


def test_name_match(repo, no_rg):
    script("skeleton.py", repo)
    f, n, s, e, src = top(repo, "parse config")[0]
    assert (f, n) == ("pkg/core.py", "parse_config") and "name" in src


def test_grep_hit_credited_to_enclosing_symbol(repo, no_rg):
    script("skeleton.py", repo)
    f, n, s, e, src = top(repo, "Println")[0]
    assert (f, n, src) == ("svc/main.go", "Server.Serve", "grep")
    ln, text = locate.locate(repo, "Println", 1)[1][0][6]  # best matching line shown with the result
    assert "fmt.Println(s.port)" in text and s <= ln <= e


def test_annotation_and_heading_match(repo, no_rg):
    script("skeleton.py", repo)
    write(repo, ".atlas/billing.md", "# billing\npkg/core.py::helper | computes invoice totals\n")
    for q in ("invoice totals", "billing"):
        f, n, s, e, src = top(repo, q)[0]
        assert (f, n, src) == ("pkg/core.py", "helper", "ann"), q


def test_stale_symbols_json_reparsed(repo, no_rg):
    script("skeleton.py", repo)
    move_functions(repo)  # new commit, skeleton not re-run
    f, n, s, e, _ = top(repo, "parse config")[0]
    assert (f, n, (s, e)) == ("pkg/core.py", "parse_config", true_range(CORE_V2, "def parse_config", "    return path"))
    write(repo, "pkg/new.py", "def brand_new_thing():\n    pass\n")  # untracked file
    assert top(repo, "brand new thing")[0][:2] == ("pkg/new.py", "brand_new_thing")


@pytest.mark.skipif(not RG, reason="no rg binary")
def test_ripgrep_matches_python_fallback(repo, monkeypatch):
    script("skeleton.py", repo)
    queries = ["Println", "handle request", "engine run job", "parse config path"]
    monkeypatch.setattr(locate.shutil, "which", lambda name: None)
    py = [top(repo, q) for q in queries]
    monkeypatch.setattr(locate.shutil, "which", lambda name: RG)
    assert [top(repo, q) for q in queries] == py


def test_synonyms_bridge_vocabulary(repo, no_rg):
    write(repo, "pkg/files.py", "def download_report(rows):\n    return rows\n")
    assert locate.expand(["export"]) == {"export": 1.0, "download": 0.5, "dump": 0.5}
    assert top(repo, "export the report")[0][:2] == ("pkg/files.py", "download_report")
