#!/usr/bin/env python3
"""Locate code for a natural-language query: top-k `path::Symbol Lx-y`, zero model tokens.

Fuses three signals with BM25, the unit being a symbol (or a file region):
  ann   text of .atlas/*.md lines (and their heading) attached to the anchors they name  x3
  name  path + symbol-name tokens                                                        x2
  grep  query-term hits in source, credited to the smallest enclosing symbol             x1
Terms: camelCase/snake_case split, light stemming, stopwords. Tests/examples x0.4.
Symbols come from .atlas/symbols.json (atlas map), re-parsed for files changed since.

Each result also shows its best matching line (most query terms), often enough to answer.

usage: locate.py <repo> "<query>" [-k 5]
"""
import argparse, json, math, re, shutil, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import skeleton as sk  # noqa: E402
from check_atlas import ANCHOR, resolve_name  # noqa: E402

WEIGHT = {"ann": 3.0, "name": 2.0, "grep": 1.0}
K1, B = 1.2, 0.75
STOP = set("""the a an and or of to in for on with from by is are be as at this that it its into when
not no use used using add added fix fixed allow support make remove handle handling should new more than via
instead only also where which what code would change changes changed repo file files function functions
answer path paths name names can does do don if so we you i my our there their them they then get set
how why after before happen happens happening work works want need like sure find show tell explain
implement implemented done doing please look where's whats""".split())


def split_ident(w):
    w = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", w)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", w).replace("_", " ").lower().split()


def stem(t):
    for suf in ("ing", "ed", "es", "e", "s"):
        if len(t) - len(suf) >= 4 and t.endswith(suf) and not (suf == "s" and t.endswith("ss")):
            return t[: -len(suf)]
    return t


def tokens(text):
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text):
        parts = split_ident(w)
        out += [stem(p) for p in parts]
        if len(parts) > 1:
            out.append(w.lower().replace("_", ""))  # whole identifier too
    return out


def query_terms(q):
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9_]*", q) if w.lower() not in STOP]
    return [t for t in dict.fromkeys(tokens(" ".join(words))) if len(t) >= 3 and t not in STOP]


def changed_files(root, since):
    out = set(sk.run(["git", "diff", "--name-only", since, "HEAD"], root).split()) if since else set()
    for line in sk.run(["git", "status", "--porcelain", "--untracked-files=all"], root).splitlines():
        out.add(line[3:].split(" -> ")[-1].strip('"'))
    return out


def load_symbols(root, files):
    atlas = Path(root, ".atlas")
    try:
        table = json.loads((atlas / "symbols.json").read_text("utf-8"))
        meta = json.loads((atlas / "meta.json").read_text("utf-8"))
    except (OSError, ValueError):
        print("(no .atlas/symbols.json: parsing everything; run atlas map)", file=sys.stderr)
        return sk.symbols(root, files)
    changed = changed_files(root, meta.get("skeleton_commit"))
    redo = [f for f in files if f not in table or f in changed]
    table.update(sk.symbols(root, redo))
    return {f: [tuple(s) for s in table[f]] for f in files}


def grep(root, files, terms):
    """[(file, line_no, text)] for lines containing any term (case-insensitive substring)."""
    fileset, hits = set(files), []
    exe = shutil.which("rg")
    if exe:
        cmd = [exe, "-n", "-i", "-F", "--no-heading", "--with-filename", "--color", "never", "-M", "400"]
        out = subprocess.run(cmd + [a for t in terms for a in ("-e", t)], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout
        for line in out.splitlines():
            f, _, rest = line.partition(":")
            ln, _, text = rest.partition(":")
            f = f.replace("\\", "/")
            f = f[2:] if f.startswith("./") else f
            if f in fileset and ln.isdigit():
                hits.append((f, int(ln), text))
        return hits
    for f in files:
        src = sk.read_src(root, f) or ""
        if not any(t in src.lower() for t in terms):
            continue
        for i, line in enumerate(src.splitlines(), 1):
            if len(line) <= 400 and any(t in line.lower() for t in terms):
                hits.append((f, i, line))
    return hits


def annotation_lines(root, syms):
    """{doc_key: [(heading, raw note line)]} for every anchor a .atlas/*.md line names."""
    out = defaultdict(list)
    for md in sorted(Path(root, ".atlas").glob("*.md")):
        if md.name.startswith("_"):
            continue
        heading = ""
        for line in md.read_text("utf-8", "replace").splitlines():
            if line.startswith("#"):
                heading = line.strip("# ")
                continue
            for m in ANCHOR.finditer(line):
                f, sym = m.group(1), m.group(2)
                if f not in syms:
                    continue
                n = resolve_name({n for n, _, _ in syms[f]}, sym) if sym else None
                out[(f, n)].append((heading, line.strip()))  # unresolvable symbol -> credited to the file
    return out


def annotations(root, syms):
    """{doc_key: annotation text}; a line's text (plus its heading) goes to every anchor it names."""
    return {k: " ".join(f"{h} {ANCHOR.sub(' ', l)}" for h, l in v) for k, v in annotation_lines(root, syms).items()}


def bm25(tf_by_doc, dl, n_docs, terms, weight=None):
    """tf_by_doc: {doc: Counter(term)}; dl: {doc: length}. Shared N so fields are comparable."""
    if not tf_by_doc:
        return {}
    avg = sum(dl[d] for d in tf_by_doc) / len(tf_by_doc) or 1
    df = Counter(t for c in tf_by_doc.values() for t in c)
    out = {}
    for d, c in tf_by_doc.items():
        s = 0.0
        for t in terms:
            if c[t]:
                idf = math.log(1 + (n_docs - df[t] + 0.5) / (df[t] + 0.5))
                s += (weight or {}).get(t, 1.0) * idf * c[t] * (K1 + 1) / (c[t] + K1 * (1 - B + B * dl[d] / avg))
        out[d] = s
    return out


# Words people use for the same code concept (a question says "export", the code says "download").
# Expansions count half. ponytail: a fixed list; learn from notes/co-occurrence if it proves too small.
SYNONYMS = [
    "export download dump", "import upload", "delete remove destroy purge", "create insert",
    "update edit modify patch", "fetch load retrieve read", "send notify email mail",
    "user account member profile", "settings config configuration preferences options",
    "auth login signin session password", "error exception failure", "price pricing cost amount total",
    "payment checkout billing invoice", "search filter query lookup", "display render view",
    "schedule cron job task queue", "image photo picture avatar thumbnail", "attachment upload",
    "translate translation i18n locale language", "permission role access authorization",
    "notification alert toast", "cache memoize", "start launch init boot", "cancel abort stop",
    "date time timezone calendar", "theme style color dark", "log logging audit trace",
]
_SYN = defaultdict(set)
for _group in SYNONYMS:
    _stems = [stem(w) for w in _group.split()]
    for _s in _stems:
        _SYN[_s].update(x for x in _stems if x != _s)


def expand(terms):
    """{term: weight}: query terms 1.0, their synonyms 0.5 (only if not already in the query)."""
    out = dict.fromkeys(terms, 1.0)
    for t in terms:
        for s in sorted(_SYN.get(t, ())):
            out.setdefault(s, 0.5)
    return out


def locate(root, query, k=5):
    root = str(Path(root).resolve())
    shown = query_terms(query)
    weight = expand(shown)
    terms = list(weight)
    files = [f for f in sk.list_files(root) if sk.LANG[Path(f).suffix.lower()] in sk.CODE]
    syms = load_symbols(root, files)
    rng = {}  # doc -> (start, end); doc = (file, symbol name | None for a file region)
    for f in files:
        for n, s, e in syms[f]:
            rng[(f, n)] = (s, e)  # duplicate names: last wins (overload impl, Rust impl block)
    n_docs = len(rng) + len(files)

    # name field: path + symbol tokens; the symbol's own name counts double (in Next.js monorepos
    # the path alone, e.g. .../surveys/[surveyId]/..., would give "survey" to thousands of symbols)
    name_tf, name_dl = {}, {}
    for f in files:
        ptoks = tokens(f)
        for key in [(f, None)] + [(f, n) for n, _, _ in syms[f]]:
            toks = ptoks + (tokens(key[1]) if key[1] else [])
            c = Counter(t for t in toks if t in terms)
            name_dl[key] = len(toks)
            if c:
                name_tf[key] = c

    # grep field: each hit line credited to the smallest enclosing symbol, else a file region
    grep_tf, grep_dl, region, best = defaultdict(Counter), {}, defaultdict(list), {}
    for f, ln, text in grep(root, files, terms):
        enc = [(e - s, n) for n, s, e in syms[f] if s <= ln <= e]
        key = (f, min(enc)[1]) if enc else (f, None)
        if not enc:
            region[f].append(ln)
        found = [t for t in terms if t in text.lower()]
        grep_tf[key].update(found)
        if len(found) > best.get(key, (0,))[0]:
            best[key] = (len(found), ln, text)  # the line to show: most query terms
    for key in grep_tf:
        s, e = rng.get(key, (min(region[key[0]] or [1]), max(region[key[0]] or [1])))
        grep_dl[key] = e - s + 1

    # annotation field
    ann_tf, ann_dl = {}, {}
    for key, text in annotations(root, syms).items():
        toks = tokens(text)
        ann_dl[key] = len(toks)
        c = Counter(t for t in toks if t in terms)
        if c:
            ann_tf[key] = c

    fields = {"ann": bm25(ann_tf, ann_dl, n_docs, terms, weight), "name": bm25(name_tf, name_dl, n_docs, terms, weight),
              "grep": bm25(grep_tf, grep_dl, n_docs, terms, weight)}
    total = defaultdict(float)
    parts = defaultdict(dict)
    for fld, scores in fields.items():
        for key, s in scores.items():
            v = WEIGHT[fld] * s * (0.4 if sk.TESTY.search(key[0]) else 1.0)
            total[key] += v
            parts[key][fld] = v
    res = []
    for key in sorted(total, key=lambda d: -total[d])[:k]:
        f, n = key
        if n:
            s, e = rng[key]
        elif region[f]:
            s, e = max(1, min(region[f]) - 5), min(max(region[f]) + 5, min(region[f]) + 60)
        else:
            s, e = 1, len((sk.read_src(root, f) or "").splitlines())
        src = "+".join(sorted(parts[key], key=lambda x: -parts[key][x]))
        if key in best:
            snip = (best[key][1], best[key][2])
        else:  # name/annotation match only: show the symbol's first line (its signature)
            lines = (sk.read_src(root, f) or "").splitlines()
            snip = (s, lines[s - 1] if 0 < s <= len(lines) else "")
        res.append((total[key], f, n, s, e, src, snip))
    return shown, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    a = ap.parse_args()
    terms, res = locate(a.repo, a.query, a.k)
    if not terms:
        print("no usable query terms")
        return 1
    print("terms: " + " ".join(terms))
    if not res:
        print("no match: fall back to grep, read the enclosing symbol")
        return 1
    for score, f, n, s, e, src, (ln, text) in res:
        print(f"{score:5.2f} {f}{'::' + n if n else ''} L{s}-{e} [{src}]  L{ln}: {text.strip()[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
