"""atlas.py (find / note / init / map) and the bash launcher, on the fixture repo from test_scripts."""
import os, shutil, subprocess, sys
from pathlib import Path

import pytest

from test_scripts import SCRIPTS, repo, write, git, BODY  # noqa: F401
import atlas  # noqa: E402

BASH = shutil.which("bash")


def run_atlas(root, *args, stdin=None):
    r = subprocess.run([sys.executable, str(SCRIPTS / "atlas.py"), *args, "--root", str(root)], input=stdin,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_find_builds_map_and_returns_code(repo):
    out = run_atlas(repo, "find", "Println")
    assert "(map built in" in out and Path(repo, ".atlas/_map.json").exists()
    assert "symbols.json" in Path(repo, ".atlas/.gitignore").read_text("utf-8")  # generated files ignored from first use
    assert "1. svc/main.go::Server.Serve L9-11" in out
    assert "fmt.Println(s.port)" in out and "    10| " in out  # the code itself, numbered: no Read needed
    assert "(map built in" not in run_atlas(repo, "find", "Println")  # second call reuses the map


def test_find_brief_without_query(repo):
    out = run_atlas(repo, "find")
    assert out.startswith("(map built in") and "central files:" in out and "## ranking" not in out


def test_find_several_queries_share_the_budget(repo):
    out = run_atlas(repo, "find", "Println", "parse config path")
    assert "## Println" in out and "## parse config path" in out
    assert "pkg/core.py::parse_config" in out
    code_lines = [l for l in out.splitlines() if l[:7].strip().isdigit() and "| " in l]
    assert len(code_lines) <= atlas.BUDGET_LINES


def test_find_stdin_heredoc_is_data(repo, tmp_path):
    out = run_atlas(repo, "find", "--stdin", stdin='Println"; touch PWNED; "\n')
    assert "Server.Serve" in out and not Path(repo, "PWNED").exists()
    assert "central files:" in run_atlas(repo, "find", "--stdin", stdin="$ARGUMENTS\n")  # unsubstituted: brief


def test_find_shows_notes_and_duplicates(repo):
    write(repo, "pkg/a.py", f"def price_total(x):\n    total = 0\n{BODY}    return total\n")
    write(repo, "pkg/b.py", f"def sum_prices(x):\n    total = 0\n{BODY}    return total\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "dupes")
    run_atlas(repo, "map")
    print(run_atlas(repo, "note", "pkg/core.py::helper | doubles the invoice amount (billing)"))
    out = run_atlas(repo, "find", "price total")
    assert "same body: pkg/b.py::sum_prices" in out or "same body: pkg/a.py::price_total" in out, out
    out = run_atlas(repo, "find", "invoice billing")
    assert "pkg/core.py::helper" in out and "note: pkg/core.py::helper ~L" in out, out


def test_note_validates_and_dedupes(repo):
    out = run_atlas(repo, "note", "pkg/core.py::run | main loop", "! pkg/core.py | env wins over config",
                    "pkg/core.py::nope | x", "missing.py | y", "no anchor here")
    assert out.startswith("added 2 note(s)"), out
    assert "pkg/core.py::nope not found" in out and "no such file: missing.py" in out and "need 'path" in out
    text = Path(repo, ".atlas/notes.md").read_text("utf-8")
    assert "pkg/core.py::Engine.run ~L" in text  # short name resolved to the canonical one, range added
    assert "! pkg/core.py | env wins over config" in text
    assert "already there" in run_atlas(repo, "note", "pkg/core.py::run | main loop")
    assert run_atlas(repo, "find", "--stdin", stdin="main loop engine\n").count("note: pkg/core.py::Engine.run") == 1


def test_init_gitignore_and_claude_md_pointer(repo):
    write(repo, "CLAUDE.md", "# project rules\n")
    assert "added a 2-line repo-atlas pointer" in run_atlas(repo, "init", "--claude-md")
    assert "already has" in run_atlas(repo, "init", "--claude-md")
    claude = Path(repo, "CLAUDE.md").read_text("utf-8")
    assert claude.startswith("# project rules\n") and claude.count("<!-- repo-atlas -->") == 1
    assert "_map.json" in Path(repo, ".atlas/.gitignore").read_text("utf-8")


def test_session_start_pointer_only_with_a_map_and_no_claude_md_pointer(repo):
    assert run_atlas(repo, "session-start") == ""  # no map yet: the hook adds nothing to the context
    run_atlas(repo, "map")
    assert "invoke the repo-atlas skill" in run_atlas(repo, "session-start")
    run_atlas(repo, "init", "--claude-md")
    assert run_atlas(repo, "session-start") == ""  # CLAUDE.md already says it


def test_session_start_suggests_the_skill_in_big_repos_before_any_map(repo, monkeypatch):
    assert atlas.session_start(str(repo)) == ""  # small repo, no map: nothing
    monkeypatch.setattr(atlas, "BIG_REPO_FILES", 2)  # the fixture's tracked code files count as a big repo
    assert atlas.session_start(str(repo)) == atlas.BIG_REPO_POINTER
    plain = repo.parent / "plain-copy"  # no .git (a home directory, say): never pushed to map everything
    shutil.copytree(repo, plain, ignore=shutil.ignore_patterns(".git", ".atlas"))
    assert atlas.session_start(str(plain)) == ""


def test_errors_never_exit_nonzero(tmp_path):
    out = run_atlas(tmp_path / "does-not-exist", "check")  # falls back to cwd/git root; must not raise
    assert isinstance(out, str)


@pytest.mark.skipif(not BASH, reason="no bash")
def test_launcher_without_python_exits_zero(tmp_path):
    r = subprocess.run([BASH, str(SCRIPTS / "atlas"), "find"], capture_output=True, text=True,
                       env={**os.environ, "PATH": str(tmp_path)})  # nothing on PATH
    assert r.returncode == 0 and "no Python 3.9+ found" in r.stdout


@pytest.mark.skipif(not BASH, reason="no bash")
def test_launcher_runs_atlas(repo):
    pydir = str(Path(sys.executable).parent)
    r = subprocess.run([BASH, str(SCRIPTS / "atlas"), "find", "Println", "--root", str(repo)], capture_output=True,
                       text=True, encoding="utf-8", env={**os.environ, "PATH": pydir + os.pathsep + os.environ["PATH"]})
    assert r.returncode == 0 and "Server.Serve" in r.stdout, r.stdout + r.stderr


def test_first_lookup_in_a_huge_repo_builds_the_map_in_the_background(repo, monkeypatch):
    import time
    monkeypatch.setenv("ATLAS_BACKGROUND_FILES", "1")  # the fixture counts as huge
    out = run_atlas(repo, "find", "Println")
    assert "being built in the background" in out and "Grep" in out
    assert "already started" in run_atlas(repo, "find", "Println")  # no second build while one runs
    for _ in range(120):  # the detached build finishes on its own
        if Path(repo, ".atlas/_map.json").exists() and not Path(repo, ".atlas/building").exists():
            break
        time.sleep(0.5)
    assert Path(repo, ".atlas/_map.json").exists() and not Path(repo, ".atlas/building").exists()
    assert "svc/main.go::Server.Serve" in run_atlas(repo, "find", "Println")  # then the map answers
