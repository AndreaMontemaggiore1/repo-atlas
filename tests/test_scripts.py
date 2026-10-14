"""Tests for skeleton.py and check_atlas.py on a tiny py/ts/go repo built on the fly.

v1 commit: pkg/core.py (parse_config, helper, Engine), web/app.ts, svc/main.go, pkg/old.py
v2 commit: parse_config moved to the bottom of core.py (drift), helper moved to
           pkg/util.py (broken symbol), pkg/old.py deleted (broken file).
"""
import json, os, re, subprocess, sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "repo-atlas" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import skeleton as sk  # noqa: E402

def pad(indent):  # makes bodies long enough to exceed --drift 15
    return "".join(f"{indent}x{i} = {i}\n" for i in range(20))

PARSE_CONFIG = f'def parse_config(path):\n    """Read config."""\n{pad("    ")}    return path\n'
HELPER = "def helper(x):\n    return x * 2\n"
ENGINE = f"class Engine:\n    def __init__(self):\n        self.n = 0\n\n    def run(self, job):\n{pad('        ')}        return job\n"

CORE_V1 = f"import os\n\n\n{PARSE_CONFIG}\n\n{HELPER}\n\n{ENGINE}"
CORE_V2 = f"import os\n\nfrom pkg.util import helper\n\n\n{ENGINE}\n\n{PARSE_CONFIG}"

APP_TS = """import { fmt } from "./fmt";

export function handleRequest(req: string): string {
  return fmt(req);
}

export class Router {
  route(path: string) {
    return handleRequest(path);
  }
}

export const toUpper = (s: string) => s.toUpperCase();
"""
FMT_TS = "export function fmt(s: string): string {\n  return `[${s}]`;\n}\n"

MAIN_GO = """package main

import "fmt"

type Server struct {
	port int
}

func (s *Server) Serve() {
	fmt.Println(s.port)
}

func main() {
	s := &Server{port: 80}
	s.Serve()
}
"""


def git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=root, env=env,
                          capture_output=True, text=True, check=True).stdout


def write(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def script(name, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def true_range(text, first_line, last_line_prefix):
    """1-based (start, end) of the block starting with `first_line` and ending at the next line starting with last_line_prefix."""
    lines = text.splitlines()
    s = next(i for i, l in enumerate(lines, 1) if l.startswith(first_line))
    e = next(i for i, l in enumerate(lines, 1) if i > s and l.startswith(last_line_prefix))
    return s, e


def skeleton_syms(root):
    """.atlas/symbols.json -> {path: {sym: (start, end)}} (duplicate names: last wins)."""
    table = json.loads(Path(root, ".atlas/symbols.json").read_text("utf-8"))
    return {f: {n: (s, e) for n, s, e in syms} for f, syms in table.items()}


def section(root, title):
    """Lines of a '## title' section of the generated .atlas/_map.md."""
    text = Path(root, ".atlas/_map.md").read_text("utf-8")
    return text.split("## " + title, 1)[1].split("\n## ", 1)[0].strip().splitlines()[1:]


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "fx"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "pkg/__init__.py", "")
    write(root, "pkg/core.py", CORE_V1)
    write(root, "pkg/old.py", "def legacy():\n    pass\n")
    write(root, "web/app.ts", APP_TS)
    write(root, "web/fmt.ts", FMT_TS)
    write(root, "svc/main.go", MAIN_GO)
    write(root, "svc/internal/db.go", "package internal\n\nfunc Open() {\n}\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "v1")
    return root


def move_functions(root):
    write(root, "pkg/core.py", CORE_V2)
    write(root, "pkg/util.py", HELPER)
    (root / "pkg/old.py").unlink()
    git(root, "add", "-A")
    git(root, "commit", "-qm", "v2: move parse_config and helper")


def write_atlas(root):
    """Annotations with correct v1 line hints taken from the skeleton."""
    syms = skeleton_syms(root)
    c = syms["pkg/core.py"]
    lines = [
        "# api",
        f"pkg/core.py::parse_config ~L{c['parse_config'][0]}-{c['parse_config'][1]} | reads cfg",
        f"pkg/core.py::helper ~L{c['helper'][0]}-{c['helper'][1]} | doubles",
        f"pkg/core.py::Engine.run ~L{c['Engine.run'][0]}-{c['Engine.run'][1]} | main loop",
        "pkg/old.py | legacy, still imported?",
        "web/app.ts::handleRequest ~L{0}-{1} | entry".format(*syms["web/app.ts"]["handleRequest"]),
        # short name on purpose: resolves to Server.Serve as a unique suffix
        "svc/main.go::Serve ~L{0}-{1} | prints port".format(*syms["svc/main.go"]["Server.Serve"]),
    ]
    write(root, ".atlas/api.md", "\n".join(lines) + "\n")
    write(root, ".atlas/INDEX.md", "# fx atlas\nareas:\n  api → api.md | everything\n")


def check(root, *flags):
    code, out = script("check_atlas.py", root, *flags)
    m = re.search(r"anchors=(\d+) broken=(\d+) drift=(\d+) stale=(\d+)", out)
    assert m, out
    return code, out, dict(zip(["anchors", "broken", "drift", "stale"], map(int, m.groups())))


# ---------------------------------------------------------------- skeleton

def test_skeleton_python_symbols_exact(repo):
    code, out = script("skeleton.py", repo)
    assert code == 0, out
    c = skeleton_syms(repo)["pkg/core.py"]
    assert c["parse_config"] == true_range(CORE_V1, "def parse_config", "    return path")
    assert c["helper"] == true_range(CORE_V1, "def helper", "    return x * 2")
    assert c["Engine.run"] == true_range(CORE_V1, "    def run", "        return job")
    assert c["Engine"][0] == true_range(CORE_V1, "class Engine", "        return job")[0]
    assert "Engine.__init__" not in c  # dunders skipped by design
    assert skeleton_syms(repo)["svc/internal/db.go"] == {"Open": (3, 4)}  # nested dir, posix path


def test_skeleton_ts_and_go_symbols(repo):
    """Regex fallback: brace-matched exact ranges, canonical Type.method names."""
    script("skeleton.py", repo)
    syms = skeleton_syms(repo)
    ts, go = syms["web/app.ts"], syms["svc/main.go"]
    last = len(APP_TS.splitlines())
    assert ts == {"handleRequest": true_range(APP_TS, "export function handleRequest", "}"),
                  "Router": true_range(APP_TS, "export class Router", "}"),
                  "Router.route": true_range(APP_TS, "  route(", "  }"),
                  "toUpper": (last, last)}  # one-liner arrow fn on the last line
    assert go == {"Server": true_range(MAIN_GO, "type Server", "}"),
                  "Server.Serve": true_range(MAIN_GO, "func (s *Server) Serve", "}"),
                  "main": true_range(MAIN_GO, "func main", "}")}


TRICKY = {
    "a.ts": ("""export interface Opts {
  url: string;
}
export class Client {
  private base = "{";
  constructor(o: Opts) {
    if (o.url) {
      this.go(o.url);
    }
  }
  async fetch<T>(
    path: string,
  ): Promise<T> {
    return fetch(`${this.base}/${path}`) as T; // }
  }
}
""", [("Opts", 1, 3), ("Client", 4, 16), ("Client.constructor", 6, 10), ("Client.fetch", 11, 15)]),
    "b.ts": ("""export default async function delay(
  ms: number,
  {signal}: Opts = {},
): Promise<void> {
  await sleep(ms);
}
class K {
  #retry(n: number): number {
    return n;
  }
}
export const clone = <T>(
  v: T,
): T => {
  return v;
};
""", [("delay", 1, 6), ("K", 7, 11), ("K.#retry", 8, 10), ("clone", 12, 16)]),
    "a.rs": ("""pub struct Pool { n: u32 }
impl Display for Pool {
    fn fmt(&self) -> String {
        format!("{}", self.n)
    }
}
pub(crate) fn make() -> Pool {
    Pool { n: 1 }
}
""", [("Pool", 1, 1), ("Pool", 2, 6), ("Pool.fmt", 3, 5), ("make", 7, 9)]),
    "A.java": ("""public final class Repo {
    public static Repo open(String p) {
        return new Repo();
    }
}
""", [("Repo", 1, 5), ("Repo.open", 2, 4)]),
    "bad.py": ("def ok():\n    return 1\nprint 'py2'\nclass K:\n    pass\n", [("ok", 1, 3), ("K", 4, 5)]),
}


HAS_TS = sk.ts_parser(".go") is not None
TRICKY.update({"app.ts": (APP_TS, None), "main.go": (MAIN_GO, None)})  # want: same as the other backend


@pytest.fixture(params=["regex", pytest.param("tree-sitter", marks=pytest.mark.skipif(not HAS_TS, reason="no tree-sitter"))])
def backend(request, monkeypatch):
    if request.param == "regex":
        monkeypatch.setattr(sk, "ts_symbols", lambda src, suffix: None)
    return request.param


@pytest.mark.parametrize("name", TRICKY)
def test_symbols_tricky(name, backend):
    src, want = TRICKY[name]
    got = sk.symbols(".", [name], {name: src})[name]
    if want is None:
        want = [(n, s, e) for n, s, e in sk.rx_symbols(src.splitlines(), sk.LANG[Path(name).suffix])]
    if backend == "tree-sitter" and name == "bad.py":
        pytest.skip("python never uses tree-sitter")
    if backend == "tree-sitter":
        assert sk.ts_symbols(src, Path(name).suffix) is not None  # really parsed, no silent fallback
    assert got == want  # impl block counts as a 2nd Pool


def test_skeleton_meta_and_ranking(repo):
    script("skeleton.py", repo)
    meta = json.loads(Path(repo, ".atlas/meta.json").read_text("utf-8"))
    head = git(repo, "rev-parse", "HEAD").strip()
    assert meta["skeleton_commit"] == head
    assert meta["synced_commit"] is None
    assert set(meta["hashes"]) >= {"pkg/core.py", "web/app.ts", "svc/main.go"}
    ranking = "\n".join(section(repo, "ranking"))
    # web/fmt.ts is imported by web/app.ts -> in=1
    assert re.search(r"web/fmt\.ts L\d+ in=1", ranking), ranking


def test_skeleton_coupled(repo):
    for i in range(3):  # core.py + fmt.ts together 3 more times (4 with v1)
        write(repo, "pkg/core.py", CORE_V1 + f"\n# {i}\n")
        write(repo, "web/fmt.ts", FMT_TS + f"// {i}\n")
        git(repo, "commit", "-qam", f"pair {i}")
    for i in range(31):  # a mass commit must not count
        write(repo, f"gen/m{i}.py", "")
    write(repo, "pkg/core.py", CORE_V1)
    write(repo, "web/fmt.ts", FMT_TS)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "mass")
    script("skeleton.py", repo)
    sec = section(repo, "coupled")
    assert sec == ["pkg/core.py <-> web/fmt.ts sup=4 conf=1.00/1.00"], sec


# ---------------------------------------------------------------- check_atlas

def test_check_clean_after_sync(repo):
    script("skeleton.py", repo)
    write_atlas(repo)
    code, out, r = check(repo, "--sync")
    assert r == {"anchors": 6, "broken": 0, "drift": 0, "stale": 0}, out
    assert code == 0
    meta = json.loads(Path(repo, ".atlas/meta.json").read_text("utf-8"))
    assert meta["synced_commit"] == git(repo, "rev-parse", "HEAD").strip()


def test_check_after_move_drift_broken_stale(repo):
    script("skeleton.py", repo)
    write_atlas(repo)
    check(repo, "--sync")
    move_functions(repo)
    code, out, r = check(repo)
    assert code == 1, out  # broken anchors -> non-zero exit
    assert "symbol not found: pkg/core.py::helper" in out
    assert "file missing: pkg/old.py" in out
    assert r["broken"] == 2, out
    # parse_config moved below Engine; Engine.run moved up: both drift
    assert re.search(r"pkg/core\.py::parse_config ~L\d+-\d+ -> \d+-\d+", out), out
    assert re.search(r"pkg/core\.py::Engine\.run ~L\d+-\d+ -> \d+-\d+", out), out
    assert r["drift"] == 2, out
    # stale = anchors on files changed since sync: the 3 core.py anchors only
    stale = out.split("STALE", 1)[1].split("\n\n", 1)[0]
    assert stale.count("pkg/core.py") == 3 and "web/app.ts" not in stale, out


def test_check_stale_on_uncommitted_edit(repo):
    script("skeleton.py", repo)
    write_atlas(repo)
    check(repo, "--sync")
    write(repo, "web/app.ts", APP_TS + "\n// touched\n")
    _, out, r = check(repo)
    assert r["stale"] == 1 and "web/app.ts::handleRequest" in out, out


def test_fix_lines_realigns_and_keeps_notes(repo):
    script("skeleton.py", repo)
    write_atlas(repo)
    check(repo, "--sync")
    move_functions(repo)
    check(repo, "--fix-lines")
    text = Path(repo, ".atlas/api.md").read_text("utf-8")
    pc = true_range(CORE_V2, "def parse_config", "    return path")
    run = true_range(CORE_V2, "    def run", "        return job")
    assert f"pkg/core.py::parse_config ~L{pc[0]}-{pc[1]} | reads cfg" in text, text
    assert f"pkg/core.py::Engine.run ~L{run[0]}-{run[1]} | main loop" in text, text
    assert "api → api.md" in Path(repo, ".atlas/INDEX.md").read_text("utf-8")  # non-ASCII survives
    _, out, r = check(repo)
    assert r["drift"] == 0 and r["broken"] == 2, out  # broken ones are not auto-fixed


def test_fix_lines_preserves_utf8(repo):
    """Annotations are UTF-8 (→, accents); --fix-lines must not corrupt them."""
    script("skeleton.py", repo)
    s, e = skeleton_syms(repo)["pkg/core.py"]["helper"]
    body = f"# area\npkg/core.py::helper ~L{s + 40}-{e + 40} | doubles it → naïve café, Ł\n"
    write(repo, ".atlas/x.md", body)
    code, out = script("check_atlas.py", repo, "--fix-lines")
    assert code == 0, out
    assert Path(repo, ".atlas/x.md").read_bytes().decode("utf-8") == body.replace(
        f"~L{s + 40}-{e + 40}", f"~L{s}-{e}")


def test_eval_gold_functions_from_changed_lines(repo):
    sys.path.insert(0, str(SCRIPTS.parents[2] / "bench"))
    import make_localization_evals as mle
    write(repo, "pkg/core.py", CORE_V1.replace("return x * 2", "return x * 3"))
    write(repo, "svc/main.go", MAIN_GO.replace("port: 80", "port: 8080"))
    git(repo, "commit", "-qam", "change helper and main")
    sha = git(repo, "rev-parse", "HEAD").strip()
    assert sorted(mle.changed_symbols(repo, sha, ["pkg/core.py", "svc/main.go"])) == ["helper", "main"]


def test_gate_denies_whole_read_of_big_file_only(repo, monkeypatch):
    import gate
    script("skeleton.py", repo)
    write(repo, "pkg/big.py", "".join(f"def f{i}():\n    return {i}\n\n" for i in range(150)))  # 450 lines
    ev = lambda **inp: {"tool_name": "Read", "tool_input": inp}
    big = str(repo / "pkg" / "big.py")
    reason = gate.decide(ev(file_path=big), repo)
    assert reason and "pkg/big.py has 450 lines" in reason and "f0 1-2" in reason and "f149 448-449" not in reason
    assert gate.decide(ev(file_path=big, offset=10, limit=20), repo) is None  # ranged read passes
    assert gate.decide(ev(file_path=str(repo / "pkg" / "core.py")), repo) is None  # small file passes
    assert gate.decide({"tool_name": "Grep", "tool_input": {"pattern": "x"}}, repo) is None
    assert gate.decide(ev(file_path=str(repo / ".atlas" / "_map.md")), repo) is None  # not code


# ---------------------------------------------------------------- v2 map: aliases, suspects, bounds

def test_js_alias_resolution(tmp_path):
    root = tmp_path
    write(root, "tsconfig.json", '{\n  // comment\n  "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"],},},\n}\n')
    alias = sk.js_aliases(root)
    files = {"src/lib/db.ts", "src/ui/index.tsx", "src/app/page.tsx"}
    assert sk.resolve_js("@/lib/db", "src/app/page.tsx", files, alias) == "src/lib/db.ts"
    assert sk.resolve_js("@/ui", "src/app/page.tsx", files, alias) == "src/ui/index.tsx"
    assert sk.resolve_js("../lib/db", "src/app/page.tsx", files, alias) == "src/lib/db.ts"
    assert sk.resolve_js("react", "src/app/page.tsx", files, alias) is None
    assert sk.resolve_js("src/lib/db", "src/app/page.tsx", files, alias) == "src/lib/db.ts"  # baseUrl


def test_pagerank_dangling_mass_conserved():
    pr = sk.pagerank(["a", "b", "c"], {"a": {"b"}})  # b and c are dangling
    assert abs(sum(pr.values()) - 1) < 1e-9 and pr["b"] > pr["a"] and abs(pr["a"] - pr["c"]) < 1e-9


BODY = "".join(f"    total += {i}\n" for i in range(6))


def test_suspects_and_alias_fan_in(repo):
    write(repo, "jsconfig.json", '{"compilerOptions": {"paths": {"@/*": ["./*"]}}}')
    write(repo, "app/dash/page.js", 'import { fmt } from "@/web/fmt";\nexport default function Page() { return fmt("x"); }\n')
    write(repo, "pkg/a.py", f"def price_total(x):\n    total = 0\n{BODY}    return total\n")
    write(repo, "pkg/b.py", f"def sum_prices(x):\n    total = 0\n{BODY}    return total\n")  # same body, other name
    write(repo, "pkg/c.py", "def price_total(y):\n    return y\n")  # same name, different body
    write(repo, "pkg/orphan.py", "def zzqx_unused_helper():\n    return 1\n")
    write(repo, "pkg/schema_types.py", "# @generated by a tool, do not edit\nX = 1\n")
    script("skeleton.py", repo)
    d = json.loads(Path(repo, ".atlas/_map.json").read_text("utf-8"))
    groups = [{(f, n) for f, n, _, _ in g} for g in d["dupes"]]
    assert {("pkg/a.py", "price_total"), ("pkg/b.py", "sum_prices")} in groups, d["dupes"]
    assert d["clashes"]["price_total"] == ["pkg/a.py", "pkg/c.py"]
    assert "pkg/orphan.py" in d["dead"] and "pkg/a.py" not in d["dead"]
    assert ["pkg/schema_types.py", "generated", 2] in d["noise"]
    assert "app/dash/page.js" in d["entries"]  # Next.js page
    fan_in = {f: i for f, _, _, i, _ in d["ranking"]}
    assert fan_in["web/fmt.ts"] == 2  # web/app.ts (relative) + app/dash/page.js (alias)
    brief = Path(repo, ".atlas/_map.md").read_text("utf-8").split(sk.BRIEF_END)[0]
    assert "duplicate bodies" in brief and "unreferenced files?" in brief


def test_map_is_bounded_on_big_repos(repo):
    for i in range(400):
        write(repo, f"mod{i // 50}/f{i}.py", "".join(f"def f{i}_{k}():\n    return {k}\n" for k in range(20)))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "many files")
    script("skeleton.py", repo)
    lines = Path(repo, ".atlas/_map.md").read_text("utf-8").splitlines()
    assert len(lines) <= 130 and max(map(len, lines)) <= 240, len(lines)
    assert len(json.loads(Path(repo, ".atlas/symbols.json").read_text("utf-8"))) >= 400  # full table kept


REACT = """export default function Admin({ id }) {
  const [x, setX] = useState(0);
  const handleSave = async () => {
    await save(x);
  };
  function onDelete(item) {
    return remove(item);
  }
  return <div onClick={handleSave}>{x}</div>;
}
"""


def test_nested_handlers_both_backends(monkeypatch):
    want = [("Admin", 1, 10), ("handleSave", 3, 5), ("onDelete", 6, 8)]
    assert sk.rx_symbols(REACT.splitlines(), "js") == want
    if sk.ts_parser(".jsx") is not None:
        assert sk.ts_symbols(REACT, ".jsx") == want


def test_go_imports_resolve_by_package_dir():
    files = {"svc/main.go", "svc/internal/db.go", "svc/internal/tx.go", "other/internal/x.py"}
    src = 'package main\n\nimport (\n\t"fmt"\n\t"example.com/svc/internal"\n)\n'
    assert sk.imports("svc/main.go", src, "go", {"__all__": files}) == {"svc/internal/db.go", "svc/internal/tx.go"}
