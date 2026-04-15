# {{TICKET_ID}} Verification Report

- **Ticket**: {{TICKET_ID}}
- **Branch / Commit**: `{{branch}}` / `{{sha}}`
- **Date**: YYYY-MM-DD
- **Author**: {{name}}

## 1. Root cause / 문제 원인
<What went wrong and why. If you are guessing, label it as a guess.
Cite related files as `path:line`.>

## 2. Change / 수정 내용
<What files changed and why — not what you considered, what you actually
applied. Bullet per file is fine.>

- `path/to/file.ts:123` — <one-line description>
- `path/to/other.tsx` — <one-line description>

## 3. Recurrence prevention / 재발 방지
<At least one of the following. If you chose to ship only a hotfix,
write "intentional omission" with the reason.>

- [ ] Root-cause fix (not a symptom patch)
- [ ] Guardrail added (validation / quality check / UI constraint)
- [ ] Regression test added or updated (must fail on the previous bug)
- [ ] Failure visibility logging (to prevent silent degradation)
- [ ] Intentional omission — reason: <...>

## 4. Verification / 검증 결과
<Only record what you actually ran. Anything you did not run goes in the
"Unverifiable" subsection below.>

| Item | Command | Result |
|---|---|---|
| Typecheck | `<typecheck command>` | ✅ / ❌ / not run |
| Tests | `<test command>` | ✅ / ❌ / not run |
| Build | `<build command>` | ✅ / ❌ / not run |
| Other | `<cmd>` | <result> |

Key output excerpts:
```
<paste only the relevant lines — never dump entire logs>
```

### Unverifiable items
Items on the pre-agreed whitelist (see working-rules.md §6) can just be
named here. Everything else must have a specific reason.

- <item> — reason: <...>

## 5. Remaining risk / 남은 리스크
<Only regression risks and areas you could not verify. NOT wishlist,
NOT nice-to-haves, NOT "could be improved" follow-ups.
If nothing applies, write "None".>

- <...>

## DoD Checklist
See `docs/dod-checklist.md` for the full list.

- [ ] Changed files committed
- [ ] Commit SHA present on base branch (`git branch --contains <sha>`)
- [ ] Build / test suite passed, or unverifiable reason given
- [ ] Result pasted into the ticket/issue comment
