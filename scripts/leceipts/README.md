# leceipts (vendored)

Upstream: https://github.com/0oooooooo0/leceipts (MIT)

## Vendored artifacts
- `check-reports.ts` — 5-section verification report linter
- `LICENSE` — upstream MIT

## Pin (2026-04-15 vendoring)
- source path: `~/.codex/leceipts/scripts/check-reports.ts`
- version: 0.1.0 (from upstream package.json)
- md5: 64a4f9bdbc1b0092558fc4bcb3c6ac21
- size: 12178 bytes
- upstream mtime: 2026-04-11 16:22

## Modifications
None. Verbatim vendor.

## Upgrade
1. Pull fresh copy from upstream (`~/.codex/leceipts/scripts/check-reports.ts`)
2. Update this README's Pin block (md5, size, mtime)
3. Run `npm run leceipts:check:all` — all reports must pass
4. Commit under `chore(leceipts): bump to <version>`

## Responsibility boundary
- **This checker** = artifact-level (verification report markdown files in `plans/`)
- **`cmux-orchestrator/scripts/leceipts-checker.py`** = runtime-level (session response format)

책임이 다르므로 두 checker는 공존한다.
