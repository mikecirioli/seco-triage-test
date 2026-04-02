# Triage Exemplars

Two reference tickets for calibration. Use these to gauge relative quality - not as templates to quote.

## EXCELLENT Example: SECO-4972

**Summary**: "Duplicate builds with same number appear when scaling HA replicas"

Why this scores well:
- Summary names the product context (HA), the symptom (duplicate builds), and the trigger (scaling replicas)
- Environment: CloudBees CI 2.440.4.27218, HA plugin 2424.v, 3 replicas
- Reproduction: 7 numbered steps with exact UI paths
- Evidence: build history screenshots, timing correlation with scaling events
- Hypothesis: "race condition in build number assignment during replica sync"
- Component assigned: cloudbees-ha
- 3 related tickets linked

Resolution: Answered (confirmed bug, fix in next release)

## NEEDS_WORK Example: SECO-5281

**Summary**: "Unify Import"

Why this scores poorly:
- Summary is 12 chars with no context (import what? from where? what fails?)
- Version: N/A
- Evidence: N/A
- Reproduction: N/A
- Hypothesis: N/A
- 3 of 7 sections are N/A without explanation
- No component assigned
- Actually a question ("how do I import?"), not a bug - but filed as Support type

Resolution: Answered (took 23 days due to back-and-forth clarification)
