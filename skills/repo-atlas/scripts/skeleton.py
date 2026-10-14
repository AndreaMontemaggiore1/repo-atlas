#!/usr/bin/env python3
"""Generate the repo map: .atlas/_map.md (bounded, model-readable), _map.json, symbols.json, meta.json.

Zero model tokens: symbols with line ranges, a centrality ranking (PageRank on the import graph,
with tsconfig/jsconfig aliases, + git churn + size), co-change, entry points and suspects
(duplicate bodies, names defined in several files, unreferenced files, generated/noise files).
No hard dependencies. Uses Python ast for .py, universal-ctags if installed,
regex fallback (brace-matched ranges) elsewhere.

usage: skeleton.py <repo> [--top 25]
"""
import argparse, ast, hashlib, json, os, posixpath, re, shutil, subprocess, sys, time
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__",
             ".next", "target", "vendor", ".atlas", ".mypy_cache", ".pytest_cache", "coverage",
             ".claude"}  # .claude/: agent config, incl. this skill when installed per project
LANG = {".py": "py", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js", ".mts": "ts", ".cts": "ts", ".ts": "ts", ".tsx": "ts", ".go": "go",
        ".java": "java", ".kt": "kt", ".rs": "rs", ".rb": "rb", ".php": "php", ".cs": "cs",
        ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".scala": "scala", ".swift": "swift",
        ".sql": "sql", ".tf": "tf", ".sh": "sh", ".yaml": "cfg", ".yml": "cfg", ".toml": "cfg",
        ".json": "cfg", ".md": "doc", ".proto": "proto", ".vue": "js", ".svelte": "js"}
CODE = {"py", "js", "ts", "go", "java", "kt", "rs", "rb", "php", "cs", "c", "cpp", "scala", "swift", "tf", "proto", "sql", "sh"}

TESTY = re.compile(r"(^|/)(tests?|spec|__tests__|examples?|fixtures?)(/|$)|(_test|\.test|\.spec)\.")

# Canonical symbol names, whatever the backend: `name` for top level, `Type.method` for
# members (Go receivers, Rust impl blocks, class bodies). check_atlas also accepts a
# unique suffix, so `Serve` still resolves to `Server.Serve`.
T, F = True, False  # is the symbol a type (members get prefixed with its name)?
RX = {  # regex fallback: lang -> [(pattern, is_type)]; groups are joined with "."
    "py": [(r"^(?:async\s+)?def\s+(\w+)", F), (r"^class\s+(\w+)", T)],  # only when ast fails
    "js": [(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\*?\s+(\w+)", F),
           (r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)", T),
           # const f = (a) => / async x => / <T>(a): R => / params continuing on the next lines
           (r"^\s*(?:export\s+)?(?:const|let)\s+(\w+)\s*(?::\s*[^=]+)?=\s*(?:async\s*)?(?:<[^>]*>\s*)?"
            r"(?:(?:\([^)]*\)|\w+)\s*(?::\s*[^=]+)?=>|\([^)]*$)", F),
           (r"^\s*(?:app|router)\.(?:get|post|put|patch|delete)\(\s*['\"]([^'\"]+)", F)],
    "go": [(r"^func\s+(?:\((?:\w+\s+)?\*?(\w+)[^)]*\)\s*)?(\w+)", F), (r"^type\s+(\w+)\s+(?:struct|interface)", T)],
    "java": [(r"^\s*(?:(?:public|private|protected|static|abstract|final|sealed)\s+)*(?:class|interface|enum|record)\s+(\w+)", T),
             (r"^\s*(?:public|private|protected)\s+(?:static\s+)?[\w<>\[\],\s]+\s+(\w+)\s*\([^;]*$", F)],
    "rs": [(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)", F),
           (r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait)\s+(\w+)", T),
           (r"^\s*impl(?:<[^>]*>)?\s+(?:[\w:<>]+\s+for\s+)?(\w+)", T)],
    "rb": [(r"^\s*(?:def|class|module)\s+([\w.:]+)", F)],
    "php": [(r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+(\w+)", T),
            (r"^\s*(?:(?:public|private|protected|static|abstract|final)\s+)*function\s+(\w+)", F)],
    "tf": [(r"^(?:resource|module|data)\s+\"([^\"]+)\"(?:\s+\"([^\"]+)\")?", F)],
    "sql": [(r"(?i)^\s*create\s+(?:or\s+replace\s+)?(?:table|view|function|procedure)\s+([\w.]+)", F)],
}
RX["ts"] = RX["js"] + [(r"^\s*(?:export\s+)?(?:declare\s+)?(?:interface|enum)\s+(\w+)", T)]
RX["kt"] = RX["java"]; RX["cs"] = RX["java"]; RX["scala"] = RX["java"]
# class-body members that need the enclosing class to be recognised (js/ts methods)
MEMBER = {"js": r"^\s+(?:(?:public|private|protected|static|async|readonly|override|abstract|get|set)\s+)*\*?(#?\w+)\s*(?:<[^>]*>)?\s*\("}
MEMBER["ts"] = MEMBER["js"]
NOT_MEMBER = {"if", "for", "while", "switch", "catch", "return", "function", "super", "await", "new"}
BRACES = {"js", "ts", "go", "java", "kt", "rs", "php", "cs", "scala", "swift", "tf", "proto"}
STRIP = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|//.*$")
STRIP_HASH = re.compile(STRIP.pattern + r"|#.*$")  # tf/php: '#' comments (in js '#x' is a private name)


def run(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout
    except Exception:
        return ""


def list_files(root):
    out = run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], root)  # + untracked
    if out.strip():
        files = [f for f in out.splitlines() if not any(p in SKIP_DIRS for p in Path(f).parts)]
    else:
        files = []
        for d, dirs, fs in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            files += [os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/") for f in fs]
    return sorted(f for f in files if Path(f).suffix.lower() in LANG)


def py_symbols(src):
    syms = []
    try:
        tree = ast.parse(src)
    except Exception:
        return None
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            syms.append((n.name, n.lineno, getattr(n, "end_lineno", n.lineno)))
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("__"):
                        syms.append((f"{n.name}.{m.name}", m.lineno, getattr(m, "end_lineno", m.lineno)))
    return syms


def block_end(i, stripped, after, base):
    """0-based last line of the block opening at line i (brace counting), None if unclear."""
    opened = False
    for j in range(i, len(stripped)):
        s = stripped[j].rstrip()
        if after[j] > base:
            opened = True  # net depth went up: the body (not a `{a}` param/default) is open
        elif opened or ("{" in s and s.endswith("}")):
            return j  # closed, or a one-line `{ ... }` block
        elif s.endswith(";"):
            return j  # bodiless statement, e.g. `const f = (x) => x * 2;`
        elif j - i >= 10:
            return None
    return None


def rx_symbols(lines, lang):
    pats = [(re.compile(p), t) for p, t in RX.get(lang, [])]
    member = re.compile(MEMBER[lang]) if lang in MEMBER else None
    braces = lang in BRACES
    strip = STRIP_HASH if lang in ("tf", "php") else STRIP
    stripped = [strip.sub("", l) for l in lines]
    before, after, d = [], [], 0
    for s in stripped:
        before.append(d); d += s.count("{") - s.count("}"); after.append(d)
    hits, stack = [], []  # hits: [name, start0, end0|None]; stack: open types (name, end0, body_depth)
    for i, line in enumerate(lines):
        while stack and stack[-1][1] is not None and stack[-1][1] < i:
            stack.pop()
        found = None
        for p, is_type in pats:
            m = p.match(line)
            if m:
                found = (".".join(g for g in m.groups() if g), is_type); break
        in_body = braces and stack and before[i] == stack[-1][2]
        if not found and member and in_body:
            m = member.match(line)
            if m and m.group(1) not in NOT_MEMBER:
                found = (m.group(1), False)
        if not found:
            continue
        name, is_type = found
        end = block_end(i, stripped, after, before[i]) if braces else None
        if in_body and "." not in name:
            name = f"{stack[-1][0]}.{name}"
        hits.append([name, i, end])
        if is_type and end is not None:
            stack.append((name, end, before[i] + 1))
    for k, h in enumerate(hits):  # no brace range: until the next symbol (old behaviour)
        if h[2] is None:
            h[2] = hits[k + 1][1] - 1 if k + 1 < len(hits) else len(lines) - 1
    return [(n, s + 1, max(s, e) + 1) for n, s, e in hits]


def ctags_symbols(root, files):
    exe = shutil.which("ctags") or shutil.which("universal-ctags")
    if not exe or "Universal" not in run([exe, "--version"], root):
        return {}
    out = run([exe, "--output-format=json", "--fields=+ne", "-f", "-"] + files, root)
    res = defaultdict(list)
    for line in out.splitlines():
        try:
            t = json.loads(line)
        except Exception:
            continue
        if t.get("kind") in ("function", "method", "class", "struct", "interface", "func", "type", "module"):
            member = t.get("scope") and t.get("scopeKind") in ("class", "struct", "interface", "impl", "trait", "type")
            name = f"{t['scope'].split('.')[-1]}.{t['name']}" if member else t["name"]
            res[t["path"].replace(os.sep, "/")].append((name, t.get("line", 0), t.get("end", t.get("line", 0))))
    return res


# Optional tree-sitter: exact ranges for non-Python languages when py-tree-sitter and the
# grammar wheels (tree-sitter-go, ...) are installed. Never downloads grammars.
TS_GRAMMARS = {".js": ("tree_sitter_javascript", "language"), ".jsx": ("tree_sitter_javascript", "language"),
               ".ts": ("tree_sitter_typescript", "language_typescript"),
               ".tsx": ("tree_sitter_typescript", "language_tsx"), ".go": ("tree_sitter_go", "language"),
               ".java": ("tree_sitter_java", "language"), ".rs": ("tree_sitter_rust", "language")}
TS_TYPES = {"class_declaration", "abstract_class_declaration", "interface_declaration", "enum_declaration",
            "record_declaration", "struct_item", "enum_item", "trait_item", "impl_item", "type_spec"}
TS_FUNCS = {"function_declaration", "generator_function_declaration", "method_definition", "method_declaration",
            "constructor_declaration", "function_item", "abstract_method_signature", "method_signature"}
TS_DESCEND = {"export_statement", "type_declaration", "mod_item", "declaration_list", "program", "source_file"}
_ts_parsers = {}


def ts_parser(suffix):
    if suffix not in _ts_parsers:
        _ts_parsers[suffix] = None
        if suffix in TS_GRAMMARS:
            try:
                import importlib, tree_sitter
                mod, fn = TS_GRAMMARS[suffix]
                lang = tree_sitter.Language(getattr(importlib.import_module(mod), fn)())
                _ts_parsers[suffix] = tree_sitter.Parser(lang)
            except Exception:
                pass
    return _ts_parsers[suffix]


def ts_symbols(src, suffix):
    """Same canonical names as rx_symbols (Type.member), exact ranges. None if unavailable."""
    parser = ts_parser(suffix)
    if parser is None:
        return None
    tree = parser.parse(src.encode("utf-8"))
    if tree.root_node.has_error:
        return None
    text = lambda n: n.text.decode("utf-8", "replace")
    out = []

    def first_type_ident(n):
        if n.type == "type_identifier":
            return text(n)
        for c in n.named_children:
            t = first_type_ident(c)
            if t:
                return t

    js = suffix in (".js", ".jsx", ".ts", ".tsx")
    FN_VALUES = ("arrow_function", "function_expression", "function")

    def arrow_consts(decl):  # const f = () => ... / const f = function () ...
        for d in decl.named_children:
            v = d.child_by_field_name("value")
            if d.type == "variable_declarator" and v is not None and v.type in FN_VALUES:
                out.append((text(d.child_by_field_name("name")), decl.start_point[0] + 1, decl.end_point[0] + 1))

    def nested(node):
        """Named functions declared inside function bodies (the handlers of a big React component),
        plain names, as rx_symbols finds them at any indentation."""
        for ch in node.named_children:
            if ch.type in ("class_declaration", "class", "abstract_class_declaration"):
                continue  # class members are walked as Type.member
            if ch.type == "lexical_declaration":
                arrow_consts(ch)
            elif ch.type in ("function_declaration", "generator_function_declaration"):
                n = ch.child_by_field_name("name")
                if n is not None:
                    out.append((text(n), ch.start_point[0] + 1, ch.end_point[0] + 1))
            nested(ch)

    def walk(node, owner):
        for ch in node.named_children:
            k, name, is_type = ch.type, None, False
            if k == "type_spec":
                body = ch.child_by_field_name("type")
                if body is not None and body.type in ("struct_type", "interface_type"):
                    name, is_type = text(ch.child_by_field_name("name")), True
            elif k == "impl_item":
                name, is_type = first_type_ident(ch.child_by_field_name("type")), True
            elif k in TS_TYPES or k in TS_FUNCS:
                n = ch.child_by_field_name("name")
                name, is_type = (text(n) if n is not None else None), k in TS_TYPES
                if k == "method_declaration" and ch.child_by_field_name("receiver") is not None:  # Go
                    name = f"{first_type_ident(ch.child_by_field_name('receiver'))}.{name}"
            elif k == "lexical_declaration" and owner is None:
                arrow_consts(ch)
                if js:
                    nested(ch)
                continue
            elif k in TS_DESCEND:
                walk(ch, owner)
                continue
            if not name:
                continue
            full = f"{owner}.{name}" if owner and "." not in name else name
            out.append((full, ch.start_point[0] + 1, ch.end_point[0] + 1))
            if is_type:
                body = ch.child_by_field_name("body")
                if body is not None:
                    walk(body, full)
            elif js:
                nested(ch)

    walk(tree.root_node, None)
    return sorted(out, key=lambda x: (x[1], -x[2]))  # document order, like rx_symbols


def read_src(root, f):
    try:
        return Path(root, f).read_bytes().decode("utf-8", "replace")
    except OSError:
        return None


def symbols(root, files, srcs=None):
    """The one symbol extraction shared by skeleton, check_atlas and locate.

    {file: [(name, start, end)]}. Chain: ast (py) | tree-sitter (others) -> ctags -> regex."""
    out, pending = {}, {}
    for f in files:
        lang = LANG.get(Path(f).suffix.lower())
        src = srcs[f] if srcs and f in srcs else read_src(root, f)
        if lang not in CODE or src is None:
            out[f] = []
            continue
        syms = py_symbols(src) if lang == "py" else ts_symbols(src, Path(f).suffix.lower())
        if syms is None:
            pending[f] = (src, lang)
        else:
            out[f] = syms
    ct = ctags_symbols(root, list(pending)) if pending else {}
    for f, (src, lang) in pending.items():
        out[f] = ct.get(f) or rx_symbols(src.splitlines(), lang)
    return out


JS_EXT = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte",
          "/index.ts", "/index.tsx", "/index.js", "/index.jsx")
JS_SPEC = re.compile(r"(?:\bfrom\s+|\brequire\(\s*|\bimport\(\s*|^\s*import\s+)['\"]([^'\"\n]+)['\"]", re.M)


def js_aliases(root):
    """compilerOptions.paths/baseUrl of tsconfig.json or jsconfig.json (Next.js `@/...`).

    {"base": dir or None, "rules": [(prefix, suffix, has_star, [target patterns])]}"""
    for name in ("tsconfig.json", "jsconfig.json"):
        try:
            txt = Path(root, name).read_text("utf-8", "replace")
            # JSON with comments and trailing commas: drop comments outside strings, then the commas
            txt = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", txt, flags=re.S)
            co = json.loads(re.sub(r",(\s*[}\]])", r"\1", txt)).get("compilerOptions") or {}
        except (OSError, ValueError, AttributeError):
            continue  # ponytail: "extends" chains are not followed; add if a real repo needs it
        base = posixpath.normpath(co.get("baseUrl") or ".")
        rules = []
        for pat, targets in (co.get("paths") or {}).items():
            pre, star, suf = pat.partition("*")
            rules.append((pre, suf, bool(star), [posixpath.normpath(posixpath.join(base, t)) for t in targets]))
        return {"base": base if co.get("baseUrl") else None, "rules": rules}
    return {"base": None, "rules": []}


def resolve_js(spec, path, files, alias):
    """Repo file a JS/TS import specifier points to (relative, tsconfig alias or baseUrl), else None."""
    cands = []
    if spec.startswith("."):
        cands.append(posixpath.normpath(posixpath.join(posixpath.dirname(path), spec)))
    else:
        for pre, suf, star, targets in alias["rules"]:
            if star and spec.startswith(pre) and spec.endswith(suf) and len(spec) >= len(pre) + len(suf):
                mid = spec[len(pre):len(spec) - len(suf)]
                cands += [t.replace("*", mid, 1) for t in targets]
            elif not star and spec == pre:
                cands += targets
        if alias["base"] is not None:
            cands.append(posixpath.normpath(posixpath.join(alias["base"], spec)))
    for c in cands:
        for ext in JS_EXT:
            if c + ext in files:
                return c + ext
    return None


def imports(path, src, lang, index, alias=None):
    """Return set of repo files imported by `path` (best effort)."""
    deps = set()
    if lang == "py":
        pkg = Path(path).parent.parts if Path(path).name == "__init__.py" else Path(path).parent.parts
        for m in re.finditer(r"^\s*from\s+(\.*)([\w.]*)\s+import\s+([\w, ()]+)|^\s*import\s+([\w.]+)", src, re.M):
            if m.group(4):
                mods = [m.group(4)]
            else:
                dots, base = len(m.group(1)), m.group(2)
                if dots:
                    parts = list(pkg[: len(pkg) - (dots - 1)] if dots > 1 else pkg)
                    base = ".".join(parts + ([base] if base else []))
                names = [n.strip() for n in m.group(3).replace("(", "").replace(")", "").split(",") if n.strip()]
                mods = [base] + [f"{base}.{n}" for n in names]
            for mod in mods:
                cands = index["__pymod__"].get(mod.strip("."))
                if cands:
                    best = min(c[0] for c in cands)
                    deps.update(f for d, f in cands if d == best)
    elif lang in ("js", "ts"):
        alias = alias or {"base": None, "rules": []}
        for m in JS_SPEC.finditer(src):
            tgt = resolve_js(m.group(1), path, index["__all__"], alias)
            if tgt:
                deps.add(tgt)
    elif lang == "go":
        godir = index.get("__godir__")
        if godir is None:  # package dir name -> its .go files, built once (a scan per import took 60s on 13k files)
            godir = index["__godir__"] = defaultdict(set)
            for f in index["__all__"]:
                if f.endswith(".go"):
                    godir[posixpath.basename(posixpath.dirname(f))].add(f)
        for m in re.finditer(r"\"([\w./-]+)\"", src.split(")", 1)[0] if "import (" in src else ""):
            deps.update(godir.get(m.group(1).split("/")[-1], ()))
    return deps - {path}


def pagerank(nodes, edges, d=0.85, it=40):
    n = len(nodes) or 1
    pr = {v: 1 / n for v in nodes}
    out = {v: [w for w in edges.get(v, ()) if w in pr] for v in nodes}
    dangling = [v for v in nodes if not out[v]]
    for _ in range(it):
        spread = d * sum(pr[v] for v in dangling) / n  # dangling mass once per iteration: O(n+e), not O(n^2)
        nxt = {v: (1 - d) / n + spread for v in nodes}
        for v in nodes:
            if out[v]:
                share = d * pr[v] / len(out[v])
                for w in out[v]:
                    nxt[w] += share
        pr = nxt
    return pr


def cochange(commits, max_files=30, min_sup=3, min_conf=0.5, top=15):
    """Files that change together: [(a, b, support, conf a->b, conf b->a)], strongest first.

    support = commits touching both; conf a->b = support / commits touching a.
    Commits with > max_files files (mass refactors, formatting) are ignored."""
    commits = [sorted(set(c)) for c in commits if 0 < len(set(c)) <= max_files]
    n = Counter(f for c in commits for f in c)
    sup = Counter(p for c in commits for p in combinations(c, 2))
    pairs = [(a, b, s, s / n[a], s / n[b]) for (a, b), s in sup.items()
             if s >= min_sup and max(s / n[a], s / n[b]) >= min_conf]
    return sorted(pairs, key=lambda p: (-max(p[3], p[4]), -p[2], p[0]))[:top]


def write_text(path, text):
    """UTF-8, LF line endings, on every Python >= 3.9 (Path.write_text(newline=) is 3.10+)."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- entry points and suspects

ENTRY_RX = re.compile(
    r"(^|/)(src/)?app/(.+/)?(page|layout|route|loading|error|not-found|template|default|global-error)\.(js|jsx|ts|tsx|mdx)$"
    r"|(^|/)(src/)?pages/.+\.(js|jsx|ts|tsx)$|^(src/)?(middleware|proxy|instrumentation)\.(js|ts)$"
    r"|(^|/)__main__\.py$|(^|/)(manage|wsgi|asgi|conftest|setup)\.py$|(^|/)bin/|\.config\.(js|cjs|mjs|ts)$"
    r"|(^|/)main\.(go|rs|c|cpp|java|kt)$")
GENERIC_NAMES = {"main", "init", "setup", "run", "get", "set", "handler", "handle", "render", "default", "index",
                 "test", "constructor", "toString", "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS",
                 "generateMetadata", "generateStaticParams", "middleware", "config", "loader", "action", "Page",
                 "Layout", "RootLayout", "metadata", "Home", "App", "load", "save", "update", "create", "delete"}
GENERATED_RX = re.compile(r"@generated|do not edit|auto-?generated|generated by", re.I)
NOISE_NAME = re.compile(r"(^|[/_. -])(copy|old|bak|backup|orig|deprecated|unused|legacy)([/_. -]|\d|$)", re.I)
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "composer.lock", "Gemfile.lock"}


def entry_points(root, srcs):
    """Files a tool or framework loads by convention (Next.js routes, __main__, bin/, configs, scripts)."""
    out = {f for f in srcs if ENTRY_RX.search(f)}
    for f, src in srcs.items():
        if f.endswith(".py") and re.search(r"^if __name__ == ['\"]__main__['\"]", src, re.M):
            out.add(f)
        elif f.endswith(".go") and re.search(r"^package main\b", src, re.M):
            out.add(f)
    try:  # files named by package.json main/bin/scripts
        pkg = json.loads(Path(root, "package.json").read_text("utf-8", "replace"))
        named = [pkg.get("main") or ""] + list((pkg.get("bin") or {}).values() if isinstance(pkg.get("bin"), dict)
                                               else [pkg.get("bin") or ""]) + list((pkg.get("scripts") or {}).values())
        for text in named:
            for tok in re.findall(r"[\w./-]+\.(?:js|mjs|cjs|ts)", str(text)):
                tok = posixpath.normpath(tok)
                if tok in srcs:
                    out.add(tok)
    except (OSError, ValueError, AttributeError):
        pass
    return out


def find_duplicates(srcs, syms, code):
    """Groups of symbols with identical bodies (whitespace-insensitive, >= 5 lines), outermost only."""
    groups = defaultdict(list)
    for f in code:
        if TESTY.search(f):
            continue
        lines = srcs[f].splitlines()
        for name, s, e in syms[f]:
            body = lines[s:e]  # signature line excluded: same body under another name is still a copy
            if len(body) >= 5:
                groups[hashlib.sha1(re.sub(r"\s+", "", "\n".join(body)).encode()).hexdigest()].append((f, name, s, e))
    dupes = [sorted(g) for g in groups.values() if len(g) > 1]
    def inside(m, others):
        return any(o[0] == m[0] and o[2] <= m[2] and m[3] <= o[3] and o != m for o in others)
    members = [m for g in dupes for m in g]
    dupes = [g for g in dupes if not all(inside(m, members) for m in g)]  # drop methods of duplicated classes
    return sorted(dupes, key=lambda g: (-(g[0][3] - g[0][2]), g[0][0]))


def name_clashes(syms, code):
    """Top-level names defined in 2-5 files (more is a framework convention, not a copy)."""
    where = defaultdict(set)
    for f in code:
        if not TESTY.search(f):
            for name, _, _ in syms[f]:
                if "." not in name and len(name) >= 4 and name not in GENERIC_NAMES:
                    where[name].add(f)
    return {n: sorted(fs) for n, fs in sorted(where.items()) if 2 <= len(fs) <= 5}


def dead_files(srcs, syms, code, fan_in, entries):
    """py/js/ts files nobody imports and whose names (symbols, file stem) appear in no other file."""
    seen = defaultdict(set)  # identifier -> files mentioning it
    for f in code:
        for w in set(re.findall(r"[A-Za-z_]\w{3,}", srcs[f])):
            seen[w].add(f)
    dead = []
    for f in code:
        if (Path(f).suffix.lower() not in (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs") or f in entries
                or TESTY.search(f) or fan_in[f] or Path(f).name == "__init__.py"):
            continue
        names = {n.split(".")[0] for n, _, _ in syms[f]} | {Path(f).stem}
        if not any(seen.get(n, set()) - {f} for n in names if len(n) >= 4):
            dead.append(f)
    return dead


def find_noise(srcs, info):
    """[(file, reason, lines)]: lockfiles, generated, minified, data dumps, backup/legacy copies."""
    out = []
    for f, src in srcs.items():
        n, lang = info[f]["lines"], info[f]["lang"]
        if Path(f).name in LOCKFILES:
            reason = "lockfile"
        elif GENERATED_RX.search("\n".join(src.splitlines()[:5])):
            reason = "generated"
        elif n and lang in ("js", "ts", "cfg") and len(src) / n > 250:
            reason = "minified?"
        elif NOISE_NAME.search(f):
            reason = "backup/legacy name"
        elif (lang == "sql" and n > 3000) or (lang == "cfg" and n > 5000):
            reason = "big data/dump"
        else:
            continue
        out.append((f, reason, n))
    return sorted(out, key=lambda x: -x[2])


# ---------------------------------------------------------------- build

MAX_PARSE_BYTES = 1_000_000  # bigger files are data or bundles: listed, not parsed


def build(root, top=25):
    """Scan the repo and write .atlas/{_map.md, _map.json, symbols.json, meta.json}. Zero model tokens.

    Returns the _map.json dict."""
    root = os.path.abspath(root)
    files = list_files(root)
    index = defaultdict(list); index["__all__"] = set(files)
    pymod = defaultdict(list)
    for f in files:
        if f.endswith(".py"):
            parts = list(Path(f).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            for k in range(len(parts)):
                pymod[".".join(parts[k:])].append((k, f))
    index["__pymod__"] = pymod
    alias = js_aliases(root)

    srcs, hashes = {}, {}
    for f in files:
        try:
            raw = Path(root, f).read_bytes()
        except OSError:
            continue
        hashes[f] = hashlib.sha1(raw).hexdigest()[:12]
        srcs[f] = raw.decode("utf-8", "replace")
    parse = [f for f in srcs if len(srcs[f]) <= MAX_PARSE_BYTES]
    syms = symbols(root, parse, srcs)
    info, edges = {}, {}
    for f, src in srcs.items():
        lang = LANG[Path(f).suffix.lower()]
        if lang in CODE and f in syms:
            edges[f] = imports(f, src, lang, index, alias)
        info[f] = {"lang": lang, "lines": len(src.splitlines()), "syms": syms.get(f, [])}

    # 12 months before HEAD's date (not today), so dormant repos and old checkouts still have history
    head_ts = run(["git", "log", "-1", "--format=%ct"], root).strip()
    since = time.strftime("%Y-%m-%d", time.gmtime(int(head_ts) - 365 * 86400)) if head_ts else "12.months"
    commits = [[f for f in c.splitlines() if f in info]
               for c in run(["git", "log", f"--since={since}", "--name-only", "--format=%x1e"], root).split("\x1e")]
    churn = Counter(f for c in commits for f in c)
    # docs/configs edited in >20% of commits (e.g. a CLAUDE.md updated every time) couple with everything
    hubs = {f for f, n in churn.items() if info[f]["lang"] not in CODE and n > 0.2 * max(1, len(commits))}
    coupled = [p for p in cochange(commits, top=None)
               if CODE & {info[p[0]]["lang"], info[p[1]]["lang"]} and not hubs & {p[0], p[1]}][:15]
    code = [f for f in info if info[f]["lang"] in CODE and f in syms]
    pr = pagerank(code, edges)
    mx_pr = max(pr.values(), default=1) or 1
    mx_ch = max(churn.values(), default=1) or 1
    mx_ln = max((info[f]["lines"] for f in code), default=1) or 1
    score = {f: 0.5 * pr[f] / mx_pr + 0.3 * churn[f] / mx_ch + 0.2 * info[f]["lines"] / mx_ln for f in code}
    for f in code:
        if TESTY.search(f):
            score[f] *= 0.4  # tests/examples rarely the answer to "where is X"
    ranked = sorted(code, key=lambda f: -score[f])
    fan_in = Counter(w for v in edges for w in edges[v])
    entries = entry_points(root, srcs)
    dupes = find_duplicates(srcs, syms, code)
    clashes = name_clashes(syms, code)
    dead = dead_files(srcs, syms, code, fan_in, entries)
    noise = find_noise(srcs, info)
    big = sorted((f for f in code if info[f]["lines"] > 1500 and not TESTY.search(f)), key=lambda f: -info[f]["lines"])

    commit = run(["git", "rev-parse", "HEAD"], root).strip() or None
    data = {
        "commit": commit, "files": len(info), "lines": sum(i["lines"] for i in info.values()),
        "code_lines": sum(info[f]["lines"] for f in code),
        "langs": Counter(info[f]["lang"] for f in code).most_common(),
        "entries": sorted(entries, key=lambda f: (-score.get(f, 0), f)),  # name breaks ties: same map every build
        "ranking": [[f, round(score[f], 3), info[f]["lines"], fan_in[f], churn[f]] for f in ranked[:50]],
        "monoliths": [[f, info[f]["lines"], len(info[f]["syms"]),
                       [[n, s, e] for n, s, e in sorted((x for x in info[f]["syms"] if "." not in x[0]),
                                                        key=lambda x: x[1] - x[2])[:3]]] for f in big],
        "dupes": [[list(m) for m in g] for g in dupes], "clashes": clashes, "dead": dead,
        "noise": [list(x) for x in noise],
        "coupled": [[a, b, s, round(ca, 2), round(cb, 2)] for a, b, s, ca, cb in coupled],
    }
    atlas = Path(root, ".atlas"); atlas.mkdir(exist_ok=True)
    write_text(atlas / "_map.md", render_map(data, top))
    write_text(atlas / "_map.json", json.dumps(data, separators=(",", ":")))
    write_text(atlas / "symbols.json", json.dumps({f: info[f]["syms"] for f in code}, separators=(",", ":")))
    meta_p = atlas / "meta.json"
    try:
        meta = json.loads(meta_p.read_text("utf-8"))
    except (OSError, ValueError):
        meta = {}
    meta.update({"skeleton_commit": commit, "hashes": hashes})
    meta.setdefault("synced_commit", None)
    write_text(meta_p, json.dumps(meta, indent=1))
    legacy = atlas / "_skeleton.md"  # v1 name; its "## files" listing grew to 50k+ tokens on big repos
    if legacy.exists():
        legacy.unlink()
    return data


BRIEF_END = "<!-- end of brief -->"


def render_map(d, top=25):
    """Bounded map (~120 lines whatever the repo size). The block before BRIEF_END is the brief."""
    def short(items, k):
        return ", ".join(items[:k]) + (f" …+{len(items) - k}" if len(items) > k else "")
    L = [f"# atlas map (generated by repo-atlas, do not edit) commit={(d['commit'] or 'none')[:10]}",
         f"{d['files']} files, {d['code_lines']} code lines; " + ", ".join(f"{k}:{v}" for k, v in d["langs"][:6])]
    if d["entries"]:
        L.append(f"entry points ({len(d['entries'])}): " + short(d["entries"], 8))
    L.append("central files: " + ", ".join(f"{f} (L{n} in={i})" for f, _, n, i, _ in d["ranking"][:6]))
    for f, n, ns, biggest in d["monoliths"][:5]:
        L.append(f"monolith {f} L{n} ({ns} syms)" + (", biggest: " + ", ".join(f"{s} {a}-{b}" for s, a, b in biggest) if biggest else ""))
    sus = [f"{len(d['dupes'])} duplicate bodies" if d["dupes"] else "",
           f"{len(d['clashes'])} names defined in several files" if d["clashes"] else "",
           f"{len(d['dead'])} unreferenced files?" if d["dead"] else "",
           f"{len(d['noise'])} generated/noise files" if d["noise"] else ""]
    if any(sus):
        L.append("suspects: " + "; ".join(s for s in sus if s) + " (details below; verify before trusting)")
    L += [BRIEF_END, "", f"## ranking (score = pagerank + churn + size; in = imported by)"]
    L += [f"{s:.2f} {f} L{n} in={i} churn={c}" for f, s, n, i, c in d["ranking"][:top]]
    if d["dupes"]:
        L += ["", "## duplicate bodies (same code in several places: change all, or find the live one)"]
        L += [" = ".join(f"{f}::{n} {s}-{e}" for f, n, s, e in g[:4]) + (f" …+{len(g) - 4}" if len(g) > 4 else "")
              for g in d["dupes"][:15]]
    if d["clashes"]:
        L += ["", "## names defined in several files"]
        L += [f"{n}: {', '.join(fs)}" for n, fs in list(d["clashes"].items())[:10]]
    if d["dead"]:
        L += ["", "## unreferenced? (not imported, names not found elsewhere; dynamic use possible)", short(d["dead"], 15)]
    if d["noise"]:
        L += ["", "## generated / noise (avoid reading or editing by hand)"]
        L += [f"{f} L{n} {r}" for f, r, n in d["noise"][:12]]
    if d["coupled"]:
        L += ["", "## coupled (changed together in git, 12 months; conf = P(other changes | this changes))"]
        L += [f"{a} <-> {b} sup={s} conf={ca:.2f}/{cb:.2f}" for a, b, s, ca, cb in d["coupled"]]
    return "\n".join(line[:240] for line in L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    t0 = time.time()
    d = build(a.repo, a.top)
    text = Path(a.repo, ".atlas", "_map.md").read_text("utf-8")
    print(f"wrote .atlas/_map.md (~{len(text) // 4} tokens), {d['files']} files, {d['lines']} lines, "
          f"{time.time() - t0:.1f}s")
    print(text.split(BRIEF_END)[0].rstrip())


if __name__ == "__main__":
    main()
