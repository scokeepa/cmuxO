#!/usr/bin/env tsx
/**
 * Verification report structure + content validator.
 *
 * Enforces the 5-section response structure on every verification report
 * file produced by code-change work. The structure is:
 *
 *   1. Root cause
 *   2. Change
 *   3. Recurrence prevention
 *   4. Verification
 *   5. Remaining risk
 *
 * The checker runs two passes against each report file:
 *
 *   PASS 1 — STRUCTURAL: all five headings must exist.
 *   PASS 2 — CONTENT:
 *     - section 3 must not be empty / placeholder-only
 *     - section 4 must not be empty AND must contain some verification
 *       evidence (command in backticks, result marker like ✅/❌, or
 *       an explicit "unverifiable" / "검증 불가" statement)
 *     - section 5 must not contain wishlist phrasing (follow-up, nice-to-have,
 *       "could be improved", etc.) — per the rule that the remaining-risk
 *       slot is for regression risks and unverified areas only.
 *
 * Both Korean and English section headings are accepted.
 *
 * Modes
 *   (default)           check reports that do NOT exist on `main` yet
 *   --all               check every report regardless of git state
 *   --file <path>       check one specific file
 *
 * Configuration
 *   --config <path>     path to verification-kit.config.json
 *                       (default: ./verification-kit.config.json)
 *
 * Config fields
 *   reportsDir          required — directory holding verification reports
 *   reportPattern       optional — filename regex (default: "-verification-report\\.md$")
 *   legacyMarker        optional — HTML comment that grandfathers legacy reports
 *                       (default: "<!-- legacy-verification-report: pre-5-section format -->")
 *   baseBranch          optional — git branch used by "new" mode (default: "main")
 *
 * Exit codes
 *   0 — all checked reports satisfy the structure and content rules
 *   1 — one or more reports have violations, or runtime error
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { execSync } from "node:child_process";

const REPO_ROOT = process.cwd();

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

interface Config {
  reportsDir: string;
  reportPattern: RegExp;
  legacyMarker: string;
  baseBranch: string;
}

const DEFAULT_CONFIG_PATH = "./verification-kit.config.json";
const DEFAULT_REPORT_PATTERN = "-verification-report\\.md$";
const DEFAULT_LEGACY_MARKER =
  "<!-- legacy-verification-report: pre-5-section format -->";

function loadConfig(configPath: string): Config {
  const abs = path.isAbsolute(configPath)
    ? configPath
    : path.join(REPO_ROOT, configPath);
  if (!fs.existsSync(abs)) {
    console.error(
      `[leceipts] config file not found: ${abs}\n` +
        `  create one with at minimum:\n` +
        `    { "reportsDir": "plans" }`,
    );
    process.exit(1);
  }
  const raw = JSON.parse(fs.readFileSync(abs, "utf8")) as Record<string, unknown>;
  if (typeof raw.reportsDir !== "string" || raw.reportsDir.length === 0) {
    console.error(`[leceipts] config missing required field: reportsDir`);
    process.exit(1);
  }
  return {
    reportsDir: raw.reportsDir,
    reportPattern: new RegExp(
      (raw.reportPattern as string | undefined) ?? DEFAULT_REPORT_PATTERN,
    ),
    legacyMarker: (raw.legacyMarker as string | undefined) ?? DEFAULT_LEGACY_MARKER,
    baseBranch: (raw.baseBranch as string | undefined) ?? "main",
  };
}

// ---------------------------------------------------------------------------
// Section definitions (accepts KR + EN headings)
// ---------------------------------------------------------------------------

type SectionDef = { label: string; pattern: RegExp };

const REQUIRED_SECTIONS: SectionDef[] = [
  {
    label: "1. Root cause / 문제 원인",
    pattern: /^#{1,6}\s*(?:1\.\s*)?(?:문제\s*원인|root\s*cause)/im,
  },
  {
    label: "2. Change / 수정 내용",
    pattern: /^#{1,6}\s*(?:2\.\s*)?(?:수정\s*내용|code\s*change|changes?)/im,
  },
  {
    label: "3. Recurrence prevention / 재발 방지",
    pattern:
      /^#{1,6}\s*(?:3\.\s*)?(?:재발\s*방지(?:\s*조치)?|recurrence[-\s]*prevention)/im,
  },
  {
    label: "4. Verification / 검증 결과",
    pattern: /^#{1,6}\s*(?:4\.\s*)?(?:검증\s*결과|verification)/im,
  },
  {
    label: "5. Remaining risk / 남은 리스크",
    pattern:
      /^#{1,6}\s*(?:5\.\s*)?(?:남은\s*리스크|remaining\s*risk|risks?)/im,
  },
];

// ---------------------------------------------------------------------------
// File discovery
// ---------------------------------------------------------------------------

function listAllReports(config: Config): string[] {
  const dir = path.join(REPO_ROOT, config.reportsDir);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((name) => config.reportPattern.test(name))
    .map((name) => path.join(dir, name));
}

/**
 * "New" reports = files that do NOT exist on the base branch yet.
 *
 * This lets historical reports written under older conventions remain
 * unflagged while enforcing the structure on new work.
 *
 * Falls back to listing all reports if git is unavailable (fresh clone,
 * detached HEAD, etc.).
 */
function listNewReports(config: Config): string[] {
  const all = listAllReports(config);
  try {
    const out = execSync(
      `git ls-tree -r --name-only ${config.baseBranch} -- ${config.reportsDir}/`,
      {
        cwd: REPO_ROOT,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      },
    );
    const onBase = new Set(
      out
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    );
    return all.filter((abs) => !onBase.has(path.relative(REPO_ROOT, abs)));
  } catch {
    console.warn(
      `[leceipts] could not resolve '${config.baseBranch}'; checking all reports`,
    );
    return all;
  }
}

// ---------------------------------------------------------------------------
// Content-level helpers
// ---------------------------------------------------------------------------

function extractSectionBody(content: string, headingPattern: RegExp): string | null {
  const lines = content.split("\n");
  let start = -1;
  let startDepth = 0;
  for (let i = 0; i < lines.length; i++) {
    if (headingPattern.test(lines[i])) {
      const m = lines[i].match(/^(#{1,6})/);
      startDepth = m ? m[1].length : 1;
      start = i + 1;
      break;
    }
  }
  if (start === -1) return null;
  const body: string[] = [];
  for (let i = start; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,6})\s/);
    if (m && m[1].length <= startDepth) break;
    body.push(lines[i]);
  }
  return body.join("\n").trim();
}

function isVacuous(body: string | null): boolean {
  if (body === null) return true;
  const stripped = body
    .replace(/<[^>]*>/g, "")
    .replace(/^[-*]\s*$/gm, "")
    .replace(/\b(TODO|TBD|FIXME|XXX)\b/gi, "")
    .trim();
  return stripped.length < 10;
}

function hasVerificationEvidence(body: string): boolean {
  if (/```|`[^`]+`/.test(body)) return true;
  if (/[✅❌⚠️🟢🟡🔴]/.test(body)) return true;
  if (/\b(passed|failed|pass|fail)\b/i.test(body)) return true;
  if (/(통과|실패|검증\s*불가|미실행|unverifiable|not\s+verified)/i.test(body)) {
    return true;
  }
  return false;
}

const WISHLIST_PATTERNS: RegExp[] = [
  /후속\s*개선/,
  /더\s*강[화하]/,
  /후속\s*티켓/,
  /향후/,
  /follow[-\s]*up/i,
  /nice\s*to\s*have/i,
  /could\s*be\s*improved/i,
  /wishlist/i,
];

function detectWishlist(body: string): string[] {
  return WISHLIST_PATTERNS.map((re) => re.exec(body)?.[0]).filter(
    (m): m is string => Boolean(m),
  );
}

// ---------------------------------------------------------------------------
// Violation detection
// ---------------------------------------------------------------------------

type Violation = { file: string; missing: string[] };

function checkFile(absPath: string, config: Config): Violation | null {
  const content = fs.readFileSync(absPath, "utf8");
  if (content.includes(config.legacyMarker)) return null;

  const missing: string[] = [];

  // Pass 1: structural — all five headings
  for (const section of REQUIRED_SECTIONS) {
    if (!section.pattern.test(content)) {
      missing.push(section.label);
    }
  }

  // Pass 2: content — only for sections that exist (avoid duplicate noise)
  const sec3Body = extractSectionBody(content, REQUIRED_SECTIONS[2].pattern);
  if (sec3Body !== null && isVacuous(sec3Body)) {
    missing.push(
      "3. Recurrence prevention — empty or placeholder-only body",
    );
  }

  const sec4Body = extractSectionBody(content, REQUIRED_SECTIONS[3].pattern);
  if (sec4Body !== null) {
    if (isVacuous(sec4Body)) {
      missing.push("4. Verification — empty or placeholder-only body");
    } else if (!hasVerificationEvidence(sec4Body)) {
      missing.push(
        "4. Verification — no command, result marker, or 'unverifiable' statement found",
      );
    }
  }

  const sec5Body = extractSectionBody(content, REQUIRED_SECTIONS[4].pattern);
  if (sec5Body !== null) {
    // Strip `<...>` placeholders before wishlist detection — instructional
    // template text is meant to be deleted, not lint-analyzed.
    const sec5Real = sec5Body.replace(/<[^>]*>/g, "");
    const hits = detectWishlist(sec5Real);
    if (hits.length > 0) {
      missing.push(
        `5. Remaining risk — wishlist phrasing detected: ${hits.join(", ")} (see working-rules.md §7)`,
      );
    }
  }

  return missing.length === 0 ? null : { file: path.relative(REPO_ROOT, absPath), missing };
}

// ---------------------------------------------------------------------------
// Arg parsing
// ---------------------------------------------------------------------------

type Mode = { kind: "new" } | { kind: "all" } | { kind: "file"; file: string };

function parseArgs(argv: string[]): { mode: Mode; configPath: string } {
  let configPath = DEFAULT_CONFIG_PATH;
  const configIdx = argv.indexOf("--config");
  if (configIdx !== -1 && argv[configIdx + 1]) configPath = argv[configIdx + 1];

  if (argv.includes("--all")) return { mode: { kind: "all" }, configPath };

  const fileIdx = argv.indexOf("--file");
  if (fileIdx !== -1) {
    const file = argv[fileIdx + 1];
    if (!file) {
      console.error("[leceipts] --file requires a path argument");
      process.exit(1);
    }
    return { mode: { kind: "file", file }, configPath };
  }

  return { mode: { kind: "new" }, configPath };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  const { mode, configPath } = parseArgs(process.argv.slice(2));
  const config = loadConfig(configPath);

  let targets: string[];
  switch (mode.kind) {
    case "all":
      targets = listAllReports(config);
      break;
    case "file":
      targets = [path.resolve(REPO_ROOT, mode.file)];
      break;
    case "new":
      targets = listNewReports(config);
      break;
  }

  if (targets.length === 0) {
    console.log("[leceipts] no reports to check");
    process.exit(0);
  }

  const violations: Violation[] = [];
  for (const file of targets) {
    if (!fs.existsSync(file)) {
      console.error(`[leceipts] file not found: ${file}`);
      process.exit(1);
    }
    const v = checkFile(file, config);
    if (v) violations.push(v);
  }

  if (violations.length === 0) {
    console.log(
      `[leceipts] OK — ${targets.length} report(s) checked, all passed`,
    );
    process.exit(0);
  }

  console.error(
    `[leceipts] FAIL — ${violations.length} report(s) have violations:\n`,
  );
  for (const v of violations) {
    console.error(`  ${v.file}`);
    for (const m of v.missing) console.error(`    - ${m}`);
  }
  console.error(
    `\nSee docs/working-rules.md §7 and templates/verification-report-template.md for the required structure.`,
  );
  process.exit(1);
}

main();
