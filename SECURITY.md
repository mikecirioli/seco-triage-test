# Security & Governance

## Kill Switch

**Stop current run:**
```bash
Ctrl+C
```

**Remove plugin:**
```bash
/plugin uninstall seco-triage
```

**Emergency - disable all CloudBees plugins:**
```bash
/plugin marketplace remove cloudbees-marketplace
```

No background processes run. The skill only executes when you explicitly invoke `/triage`.

## Rule of Two Status

**Assessment:** 0/3 properties satisfied → No Security review required

- ✗ Untrustworthy inputs (reads internal Jira, standard practice)
- ✗ Sensitive data access (internal bug tracker, no PII/credentials)
- ✗ Consequential actions (advisory only, no automated modifications)

## Data Handling

**What gets logged:**
- Ticket key, score, verdict, grader names, timestamp
- User hash (sha256 of email, first 12 chars)

**What NEVER gets logged:**
- Ticket descriptions, summaries, or content
- Customer names, emails, or identifiers
- Log snippets, URLs, or internal hostnames

## Incident Response

If the skill does something unexpected:

1. **Stop it:** Ctrl+C or `/plugin uninstall seco-triage`
2. **Report:** security@cloudbees.com or #topic-seco-triage-skill
3. **Preserve logs:** Keep the terminal output for investigation

## Contacts

- **Owner:** Mike Cirioli (mcirioli@cloudbees.com)
- **Support:** #topic-seco-triage-skill on Slack
- **Security:** security@cloudbees.com
