# SECO Ticket Template Reference

Standard template sections for CloudBees SECO (Support Engineering Collaboration) tickets. 97% of SECOs use this template.

## Required Sections

**Case Summary** - Brief overview of the issue and customer context.

**Environment Information** - Must include:
- Product: (CloudBees CI, CloudBees CD/RO, Unify, etc.)
- Version: (specific version number, e.g., 2.504.3.28224)
- Plugins involved and versions, if applicable

**Symptom** - What the end user is experiencing. Should be specific and observable.

**Evidence/Detail** - Logs, screenshots, error messages, stack traces, config snippets. The more inline evidence, the faster triage.

**Reproduction Steps** - Numbered steps to reproduce. If not reproducible, explain what was tried and frequency of occurrence.

**Documentation Consulted** - Links to KB articles, docs, or community posts already checked. Shows due diligence.

**Hypothesis** - Support engineer's best guess at root cause. Even a rough hypothesis helps engineering prioritize.

**Next Steps** - What's been tried, what's planned, what's blocked.

**What Help is Needed** - Specific ask: root cause analysis? workaround? config review? patch? The more specific, the faster routing.

## Common Anti-Patterns
- "N/A" in Evidence, Reproduction, or Hypothesis without explanation
- "To be updated" placeholder descriptions
- Vague summaries without product context ("Authentication issue")
- Performance complaints without timing data
- Error mentions without inline error text
