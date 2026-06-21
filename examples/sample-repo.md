# Repo structure

_/home/user/acme-app · 412 files · 3.1MB_

**Grade B**: 3 junk artifacts, 18.4KB reclaimable across 412 files.

| Metric | Value |
| --- | --- |
| Files scanned | 412 |
| Repo size (tracked) | 3.1MB |
| Reclaimable size | 18.4KB |
| Dead / junk artifacts | 3 |
| Largest file | app/dashboard/page.tsx (2,140 lines) |

### Size by area

| Item | | Value |
| --- | :-- | ---: |
| app | `████████████` | 1.4MB |
| components | `███████·····` | 820KB |
| lib | `████········` | 410KB |
| public | `██··········` | 280KB |
| docs | `█···········` | 90KB |

## Findings (4)

### 1. [HIGH] Committed junk / build artifacts
- **Evidence:** 3 junk files tracked (logs, .DS_Store, .orig/.bak/.tmp).
- **Fix:** Remove and add to .gitignore. These inflate clones and every agent's file listing.
- **At:** build.log, src/.DS_Store, lib/api/client.ts.orig

### 2. [MEDIUM] Orphan library modules (no inbound imports)
- **Evidence:** 6 library modules under app/components/lib appear unreferenced (candidates; verify dynamic imports first).
- **Fix:** Confirm with knip/ts-prune, then delete behind a typecheck+lint gate. Dead modules tax every repo-wide search.
- **At:** lib/legacy/format-old.ts, components/old/Banner.tsx, lib/unused-helpers.ts

### 3. [LOW] Oversized source files
- **Evidence:** 4 files exceed 700 lines; the largest is 2,140 lines.
- **Fix:** Split god-files by responsibility. Smaller files mean cheaper, more precise agent reads and edits.
- **At:** app/dashboard/page.tsx (2,140 lines), lib/api/client.ts (980 lines)

### 4. [LOW] Large commented-out code blocks
- **Evidence:** 5 files contain a commented-out code block of >= 10 lines.
- **Fix:** Delete dead code; git history is the archive. Commented blocks mislead agents and bloat context.
- **At:** lib/api/client.ts, components/Form.tsx

---

Static pass. Pair with session evidence (--mode both) to rank by agent friction.
Example output, illustrative numbers. Orphan detection targets JS/TS imports.
