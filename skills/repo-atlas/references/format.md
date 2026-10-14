# Atlas format

## Files
```
.atlas/
  notes.md        # written via `atlas note` (or by hand): one line per fact, committed
  INDEX.md, <area>.md   # optional hand-written notes, same line grammar; also searched by find
  _map.md         # generated: bounded overview (brief first) — do not edit
  _map.json       # generated: the same data, structured (used by find)
  symbols.json    # generated: every symbol with its line range
  meta.json       # generated: map commit, notes sync commit, file hashes
  .gitignore      # written by `atlas init`: ignores the generated files
```
Files starting with `_` and the JSON files are rebuilt for free; only notes carry knowledge.

## Line grammar
```
[prefix] <anchor> [~L<start>-<end>] | <note>
```
- `anchor` = `path`, `path::Symbol` or `path::Class.method` (a unique `method` alone also resolves)
- `~L` = line hint; it drifts, the symbol is authoritative (`atlas check --fix-lines` realigns)
- prefixes: `!` trap, `?` unverified, `x` dead/ignore, `→` flow step, `@` entry point
- telegraphic: verbs and nouns, the words a user would search with

## Examples
```
src/billing/invoice.py::Invoice.total ~L120-180 | VAT and discounts applied here, not in cart
! src/api/routes.js | auth checked per route, no global middleware
x src/legacy/ | not imported anywhere since the v2 rewrite
app/api/sync/route.js::parseIcal ~L16-38 | live copy; app/api/sync-all has a stale duplicate
→ app/checkout/page.jsx::Checkout.submit
→ app/api/orders/route.js::POST
? lib/export.js::toCsv | probably admin-only, auth check not seen
```

## What not to write
- what `_map.md` or the code already says (file lists, sizes, signatures)
- anything you did not read (or mark it `?`)
- paragraphs: if it needs one, it belongs in real docs
