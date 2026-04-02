# seco-triage Test Marketplace

**Status:** Test repository for marketplace structure validation before official CloudBees org repo creation.

## What This Is

Test installation of the seco-triage plugin - a pre-triage quality assessment tool for CloudBees support tickets (SECO) and engineering tickets (BEE).

**Purpose:** Scores tickets against 25+ deterministic graders and provides actionable feedback before human triage.

**Type:** Interactive CLI skill (not autonomous)

**Rule of Two:** 0/3 properties → No Security review required

See [SECURITY.md](SECURITY.md) for governance details.

## Test Installation

```bash
/plugin marketplace add mikecirioli/seco-triage-test
/plugin install seco-triage
/reload-plugins
```

## Test Usage

```bash
/triage SECO-5311
```

## Validation Checklist

- [x] Marketplace.json structure (`.claude-plugin/marketplace.json`)
- [x] Plugin loads successfully
- [ ] Full triage run completes
- [ ] Hooks fire (update check, install tracking)
- [ ] Learning PR flow works
- [ ] Insights command works
- [ ] Support command works

---

**Note:** This repo will be deleted after successful validation. Official repo: `cloudbees/seco-triage` (pending)
