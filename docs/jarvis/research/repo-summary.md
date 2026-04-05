# JARVIS 레포 조사 요약

> 참조. 상세는 knowledge/raw/2026-04-02_repo-deep-research-full.md

## 조사 레포 20개 (14 + 6 추가)

### 핵심 레포 — Phase 1 직접 참조
| 레포 | Stars | 도입 패턴 |
|------|-------|----------|
| obra/superpowers | 130K | 4상태 보고, TDD, "Do Not Trust", 2단계 리뷰, Red Flags |
| thedotmack/claude-mem | 44K | 5 Hook 생명주기, Worker Service, FTS5, Progressive Disclosure |
| paperclipai/paperclip | - | Heartbeat, Budget, Atomic checkout, Approval workflow |
| garrytan/gstack | - | GATE 5단계, /freeze, /investigate, /learn, /autoplan |
| nizos/tdd-guard | 1,956 | TDD hook 실제 구현체 (Iron Law #2 참조) |
| Dicklesworthstone/agent_farm | 769 | Lock 조율, heartbeat, context 감시, 병렬 에이전트 |
| sorihanul/Jarvis_Starter_Pack | 5 | 3계층 메모리, GC 4등급, 2레인, Pipeline Contract |

### Obsidian 생태계 — Phase 2+ 참조
| 레포 | Stars | 도입 패턴 |
|------|-------|----------|
| basicmachines-co/basic-memory | 2,741 | Entity/Observation/Relation, 양방향 Sync, memory:// |
| axtonliu/obsidian-visual-skills | 2,074 | Excalidraw/Mermaid/Canvas |
| YishenTu/claudian | 5,628 | VaultFileAdapter, JSONL 세션 |
| jylkim/obsidian-sync | 신규 | 멀티 에이전트 세션 동기화 |
| kepano/obsidian-skills | - | 공식 Obsidian MD/Bases/Canvas/CLI |

### Claude Code 소스 기반 (S1~S12)
상세: [claude-source-findings.md](claude-source-findings.md)
