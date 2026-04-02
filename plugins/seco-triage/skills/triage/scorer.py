#!/usr/bin/env python3
"""
Triage scorer - evaluates ticket quality using grader-based scoring.

Reads grader definitions and weights from knowledge/scorer/ config files.
Outputs structured JSON to stdout for consumption by the skill prompt.

Usage:
  python3 scorer.py --ticket ticket.json --config knowledge/scorer/
  python3 scorer.py --ticket ticket.json  # defaults to knowledge/scorer/ relative to script
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path


def load_config(config_dir):
    config_dir = Path(config_dir)
    with open(config_dir / "graders.json") as f:
        graders_config = json.load(f)
    with open(config_dir / "weights.json") as f:
        weights_config = json.load(f)
    with open(config_dir / "components.json") as f:
        components_config = json.load(f)
    return graders_config, weights_config, components_config


# --- ADF text extraction ---

def extract_text(adf_node):
    if not adf_node:
        return ""
    if isinstance(adf_node, str):
        return adf_node
    if isinstance(adf_node, dict):
        if adf_node.get("type") == "text":
            return adf_node.get("text", "")
        return " ".join(extract_text(c) for c in adf_node.get("content", []))
    if isinstance(adf_node, list):
        return " ".join(extract_text(c) for c in adf_node)
    return ""


def extract_sections(description):
    sections = {}
    if not description or not isinstance(description, dict):
        return sections
    current_heading = None
    for node in description.get("content", []):
        if node.get("type") == "heading":
            heading_text = extract_text(node).strip().lower()
            if heading_text:
                current_heading = heading_text
                if current_heading not in sections:
                    sections[current_heading] = ""
        elif current_heading:
            text = extract_text(node).strip()
            sections[current_heading] = (sections[current_heading] + " " + text).strip()
    return sections


MAJOR_SECTIONS = {"case summary", "environment", "symptom", "evidence", "detail",
                   "reproduction", "hypothesis", "next steps", "documentation",
                   "help", "what help"}


def find_section(sections, *keywords):
    headings = list(sections.keys())
    for i, heading in enumerate(headings):
        if any(kw in heading for kw in keywords):
            content = sections[heading]
            if not content.strip():
                for j in range(i + 1, len(headings)):
                    sub = headings[j]
                    if any(ms in sub for ms in MAJOR_SECTIONS):
                        break
                    content = (content + " " + sections[sub]).strip()
            return content
    return ""


def is_na(text):
    if not text:
        return True
    return text.strip().lower() in ("n/a", "na", "n / a", "-", "none", "")


def is_stub(text):
    if not text:
        return True
    cleaned = text.strip().lower()
    return any(s in cleaned for s in ["to be updated", "tbd", "placeholder", "will update"])


def suggest_components(text, components_config):
    text_lower = text.lower()
    return [comp for comp, keywords in components_config["components"].items()
            if any(kw in text_lower for kw in keywords)]


# --- Grader evaluation ---

def evaluate_graders(issue, graders_config):
    fields = issue.get("fields", {})
    key = issue.get("key", "?")
    is_seco = key.startswith("SECO-")
    summary = fields.get("summary", "")
    description = fields.get("description")
    components = fields.get("components", []) or []
    priority_raw = fields.get("priority") or ""
    priority = priority_raw.get("name", "") if isinstance(priority_raw, dict) else str(priority_raw)

    full_text = extract_text(description)
    sections = extract_sections(description)
    text_lower = (full_text + " " + summary).lower()

    has_headings = any(n.get("type") == "heading" for n in (description or {}).get("content", []))

    # Fallback: plain text template detection
    if not has_headings and full_text:
        template_markers = ["case summary", "environment", "symptom", "evidence", "reproduction"]
        has_template_text = sum(1 for m in template_markers if m in text_lower) >= 3
        if has_template_text:
            has_headings = True
            if not sections:
                section_names = ["case summary", "environment", "symptom", "evidence",
                                 "reproduction", "hypothesis", "next steps", "documentation",
                                 "help", "detail"]
                for sname in section_names:
                    idx = text_lower.find(sname)
                    if idx >= 0:
                        next_idx = len(full_text)
                        for other in section_names:
                            if other == sname:
                                continue
                            oidx = text_lower.find(other, idx + len(sname))
                            if 0 < oidx < next_idx:
                                next_idx = oidx
                        content = full_text[idx + len(sname):next_idx].strip().lstrip(":").strip()[:500]
                        sections[sname] = content

    env = find_section(sections, "environment")
    symptom = find_section(sections, "symptom")
    evidence = find_section(sections, "evidence", "detail")
    repro = find_section(sections, "reproduction", "repro")
    hypothesis = find_section(sections, "hypothesis")
    docs = find_section(sections, "documentation", "consulted")
    help_needed = find_section(sections, "help", "needed")
    zendesk = extract_text(fields.get("customfield_12400", "")).strip()

    graders = {}
    blocked = False
    grader_defs = graders_config["graders"]

    # CRITICAL: stub
    stub = is_stub(full_text) or len(full_text.strip()) < 50
    graders["description_not_stub"] = {
        "fired": stub, "severity": "CRITICAL", "category": "template_completeness",
        "message": grader_defs["description_not_stub"]["message"] if stub else None
    }
    if stub:
        blocked = True

    # Template structure
    template_severity = "CRITICAL" if is_seco else "ERROR"
    graders["has_template_structure"] = {
        "fired": not has_headings, "severity": template_severity, "category": "template_completeness",
        "message": grader_defs["has_template_structure"]["message"] if not has_headings else None
    }
    if not has_headings and is_seco:
        blocked = True

    # Symptom
    symptom_missing = is_na(symptom) and not stub
    graders["symptom_present"] = {
        "fired": symptom_missing, "severity": "CRITICAL", "category": "template_completeness",
        "message": grader_defs["symptom_present"]["message"] if symptom_missing else None
    }
    if symptom_missing and has_headings and is_seco:
        blocked = True

    # Product
    product_present = bool(re.search(r'product\s*:\s*\S', env, re.I)) if env else False
    if not product_present:
        product_keywords = grader_defs["environment_product"]["product_keywords"]
        product_present = any(kw in text_lower for kw in product_keywords)
    graders["environment_product"] = {
        "fired": not product_present, "severity": "CRITICAL", "category": "template_completeness",
        "message": grader_defs["environment_product"]["message"] if not product_present else None
    }
    if not product_present and has_headings and not stub and is_seco:
        blocked = True

    # Version
    version_present = bool(re.search(r'\d+\.\d+\.\d+', full_text))
    graders["environment_version"] = {
        "fired": not version_present, "severity": "ERROR", "category": "template_completeness",
        "message": grader_defs["environment_version"]["message"] if not version_present else None
    }

    # N/A sections
    target_sections = grader_defs["na_sections"]["target_sections"]
    na_count = sum(1 for name, content in sections.items()
                   if is_na(content) and any(kw in name for kw in target_sections))
    graders["na_sections"] = {
        "fired": na_count > 0, "severity": "ERROR", "category": "template_completeness",
        "message": grader_defs["na_sections"]["message_template"].format(count=na_count) if na_count > 0 else None,
        "count": na_count
    }

    # Hypothesis
    graders["hypothesis_present"] = {
        "fired": is_na(hypothesis), "severity": "WARNING", "category": "template_completeness",
        "message": grader_defs["hypothesis_present"]["message"] if is_na(hypothesis) else None
    }

    # Docs
    docs_present = not is_na(docs) or "http" in (docs or "")
    graders["docs_consulted"] = {
        "fired": not docs_present, "severity": "WARNING", "category": "template_completeness",
        "message": grader_defs["docs_consulted"]["message"] if not docs_present else None
    }

    # Evidence
    graders["evidence_present"] = {
        "fired": is_na(evidence), "severity": "ERROR", "category": "evidence_quality",
        "message": grader_defs["evidence_present"]["message"] if is_na(evidence) else None
    }

    # Logs present (text indicators + attachments)
    log_indicators = grader_defs["logs_present"]["log_indicators"]
    has_log_text = any(ind in text_lower for ind in log_indicators)
    attachments = fields.get("attachment", []) or []
    has_log_attachment = any(
        any(ind in (a.get("filename", "") + " " + a.get("mimeType", "")).lower() for ind in log_indicators)
        for a in attachments
    ) if attachments else False
    has_logs = has_log_text or has_log_attachment or len(attachments) > 0
    graders["logs_present"] = {
        "fired": not has_logs and not stub, "severity": "ERROR", "category": "evidence_quality",
        "message": grader_defs["logs_present"]["message"] if (not has_logs and not stub) else None
    }

    # Error has message
    error_keywords = grader_defs["error_has_message"]["error_mention_keywords"]
    has_error_mention = any(w in text_lower for w in error_keywords)
    has_error_text = bool(re.search(grader_defs["error_has_message"]["error_text_pattern"], full_text))
    graders["error_has_message"] = {
        "fired": has_error_mention and not has_error_text, "severity": "ERROR", "category": "evidence_quality",
        "message": grader_defs["error_has_message"]["message"] if (has_error_mention and not has_error_text) else None
    }

    # Performance has metrics
    perf_keywords = grader_defs["performance_has_metrics"]["perf_keywords"]
    perf_exclude = ["session", "logout", "log out", "logged out", "sign out", "session terminated"]
    has_perf = any(w in text_lower for w in perf_keywords)
    has_perf_exclusion = any(w in text_lower for w in perf_exclude)
    has_metrics = bool(re.search(grader_defs["performance_has_metrics"]["metrics_pattern"], full_text))
    perf_fired = has_perf and not has_metrics and not has_perf_exclusion
    graders["performance_has_metrics"] = {
        "fired": perf_fired, "severity": "ERROR", "category": "evidence_quality",
        "message": grader_defs["performance_has_metrics"]["message"] if perf_fired else None
    }

    # Reproduction present
    bug_keywords = grader_defs["reproduction_present"]["bug_keywords"]
    bug_like = any(w in text_lower for w in bug_keywords)
    graders["reproduction_present"] = {
        "fired": bug_like and is_na(repro), "severity": "ERROR", "category": "evidence_quality",
        "message": grader_defs["reproduction_present"]["message"] if (bug_like and is_na(repro)) else None
    }

    # Reproduction structured
    has_numbered_steps = bool(re.search(r'\d+[\.\)]\s', repro or "")) if repro else False
    not_reproducible_markers = ["not reproducible", "not able to reproduce", "cannot reproduce",
                                "unable to reproduce", "could not reproduce", "can't reproduce"]
    is_not_reproducible = any(m in (repro or "").lower() for m in not_reproducible_markers)
    repro_structured_fired = not is_na(repro) and not has_numbered_steps and len(repro or "") < 100 and not is_not_reproducible
    graders["reproduction_structured"] = {
        "fired": repro_structured_fired,
        "severity": "WARNING", "category": "evidence_quality",
        "message": grader_defs["reproduction_structured"]["message"] if repro_structured_fired else None
    }

    # Intermittent has pattern
    intermittent_kw = grader_defs["intermittent_has_pattern"]["intermittent_keywords"]
    pattern_kw = grader_defs["intermittent_has_pattern"]["pattern_keywords"]
    intermittent = any(w in text_lower for w in intermittent_kw)
    has_pattern = any(w in text_lower for w in pattern_kw)
    graders["intermittent_has_pattern"] = {
        "fired": intermittent and not has_pattern, "severity": "WARNING", "category": "evidence_quality",
        "message": grader_defs["intermittent_has_pattern"]["message"] if (intermittent and not has_pattern) else None
    }

    # Regression context
    regression_kw = grader_defs["regression_context"]["regression_keywords"]
    has_regression = any(w in text_lower for w in regression_kw)
    graders["regression_context"] = {
        "fired": bug_like and not has_regression, "severity": "WARNING", "category": "evidence_quality",
        "message": grader_defs["regression_context"]["message"] if (bug_like and not has_regression) else None
    }

    # Change context
    change_kw = grader_defs["change_context"]["change_keywords"]
    has_change = any(w in text_lower for w in change_kw)
    graders["change_context"] = {
        "fired": bug_like and not has_change, "severity": "WARNING", "category": "evidence_quality",
        "message": grader_defs["change_context"]["message"] if (bug_like and not has_change) else None
    }

    # Component assigned
    graders["component_assigned"] = {
        "fired": len(components) == 0, "severity": "WARNING", "category": "routing_readiness",
        "message": None  # populated below with suggestions
    }

    # Summary specific
    graders["summary_specific"] = {
        "fired": len(summary) < 30, "severity": "WARNING", "category": "routing_readiness",
        "message": grader_defs["summary_specific"]["message_template"].format(length=len(summary)) if len(summary) < 30 else None
    }

    # Summary descriptive
    graders["summary_descriptive"] = {
        "fired": 30 <= len(summary) < 50, "severity": "WARNING", "category": "routing_readiness",
        "message": grader_defs["summary_descriptive"]["message_template"].format(length=len(summary)) if 30 <= len(summary) < 50 else None
    }

    # Zendesk linked
    graders["zendesk_linked"] = {
        "fired": not zendesk, "severity": "ERROR", "category": "routing_readiness",
        "message": grader_defs["zendesk_linked"]["message"] if not zendesk else None
    }

    # Ops/admin request misrouted to SECO
    ops_keywords = grader_defs["ops_request_misrouted"]["ops_keywords"]
    is_ops_request = any(kw in text_lower for kw in ops_keywords)
    ticket_key = issue.get("key", "")
    is_seco = ticket_key.startswith("SECO")
    graders["ops_request_misrouted"] = {
        "fired": is_ops_request and is_seco, "severity": "WARNING", "category": "routing_readiness",
        "message": grader_defs["ops_request_misrouted"]["message"] if (is_ops_request and is_seco) else None
    }

    # Issue type clear
    bug_words = sum(1 for w in ["error", "exception", "fails", "broken", "crash", "bug"] if w in text_lower)
    q_words = sum(1 for w in ["how to", "clarification", "explain", "what is"] if w in text_lower)
    rfe_words = sum(1 for w in ["should", "could", "enhancement", "feature request", "improve"] if w in text_lower)
    types_present = sum(1 for v in [bug_words, q_words, rfe_words] if v > 0)
    graders["issue_type_clear"] = {
        "fired": types_present != 1, "severity": "WARNING", "category": "classification_clarity",
        "message": grader_defs["issue_type_clear"]["message"] if types_present != 1 else None
    }

    # Ask specific - also check custom "Type of Help" field (customfield variants)
    type_of_help = ""
    for cf_key, cf_val in fields.items():
        if cf_key.startswith("customfield_") and cf_val:
            if isinstance(cf_val, dict):
                cf_text = cf_val.get("value", "") or extract_text(cf_val)
            else:
                cf_text = str(cf_val) if cf_val else ""
            if cf_text and any(kw in cf_text.lower() for kw in ["debug", "troubleshoot", "root cause", "investigate", "assistance", "help"]):
                type_of_help = cf_text
                break
    ask_has_content = (not is_na(help_needed) and len((help_needed or "").strip()) >= 20) or len(type_of_help.strip()) > 0
    graders["ask_specific"] = {
        "fired": not ask_has_content,
        "severity": "WARNING", "category": "classification_clarity",
        "message": grader_defs["ask_specific"]["message"] if not ask_has_content else None
    }

    # Impact assessment
    impact_kw = grader_defs["impact_assessment"]["impact_keywords"]
    has_impact = any(w in text_lower for w in impact_kw)
    graders["impact_assessment"] = {
        "fired": not has_impact, "severity": "WARNING", "category": "classification_clarity",
        "message": grader_defs["impact_assessment"]["message"] if not has_impact else None
    }

    # Related tickets
    jira_links = fields.get("issuelinks", []) or []
    has_inline_links = bool(re.search(grader_defs["related_tickets_linked"]["inline_pattern"], full_text))
    has_links = len(jira_links) > 0 or has_inline_links
    graders["related_tickets_linked"] = {
        "fired": not has_links, "severity": "WARNING", "category": "classification_clarity",
        "message": grader_defs["related_tickets_linked"]["message"] if not has_links else None
    }

    return graders, blocked, text_lower


def compute_score(graders, blocked, weights_config):
    categories = {}
    for cat, cat_config in weights_config["categories"].items():
        max_score = cat_config["max_score"]
        score = max_score
        failed = []
        for grader_name, deduction in cat_config["deductions"].items():
            grader = graders.get(grader_name, {})
            if grader.get("fired"):
                if grader_name == "na_sections":
                    actual_deduction = min(deduction * grader.get("count", 1), 1.0)
                else:
                    actual_deduction = deduction
                score -= actual_deduction
                failed.append(grader_name)
        score = max(0, score)
        categories[cat] = {"score": round(score, 2), "max": max_score, "failed": failed}

    overall = sum(c["score"] for c in categories.values())

    verdicts = weights_config["verdicts"]
    if blocked:
        overall = min(overall, verdicts["BLOCK"]["score_cap"])
        verdict = "BLOCK"
    elif overall >= verdicts["EXCELLENT"]["threshold"]:
        verdict = "EXCELLENT"
    elif overall >= verdicts["GOOD"]["threshold"]:
        verdict = "GOOD"
    elif overall >= verdicts["FAIR"]["threshold"]:
        verdict = "FAIR"
    else:
        verdict = "NEEDS_WORK"

    return round(overall, 1), verdict, categories


def score_ticket(issue, graders_config, weights_config, components_config):
    graders, blocked, text_lower = evaluate_graders(issue, graders_config)
    overall, verdict, categories = compute_score(graders, blocked, weights_config)

    fields = issue.get("fields", {})
    resolution_raw = fields.get("resolution") or ""
    resolution = resolution_raw.get("name", "") if isinstance(resolution_raw, dict) else str(resolution_raw)
    status_raw = fields.get("status") or ""
    status = status_raw.get("name", "") if isinstance(status_raw, dict) else str(status_raw)

    # Component suggestions
    suggested = suggest_components(text_lower, components_config)
    # If multiple components are suggested, root cause is ambiguous - don't penalize
    if len(suggested) > 1:
        graders["component_assigned"]["fired"] = False
        graders["component_assigned"]["message"] = None
    elif graders["component_assigned"]["fired"] and suggested:
        graders["component_assigned"]["message"] = f"No component assigned. Suggested: {', '.join(suggested)}"
    elif graders["component_assigned"]["fired"]:
        graders["component_assigned"]["message"] = "No component assigned."

    flags = [{"grader": name, "severity": g["severity"], "message": g["message"], "category": g["category"]}
             for name, g in graders.items() if g["fired"] and g.get("message")]

    return {
        "session_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "scorer_version": graders_config.get("_version", "unknown"),
        "key": issue.get("key", "?"),
        "summary": fields.get("summary", "")[:80],
        "score": overall,
        "verdict": verdict,
        "blocked": blocked,
        "resolution": resolution or status,
        "categories": categories,
        "graders_fired": [name for name, g in graders.items() if g["fired"]],
        "flags": flags,
        "component_suggestions": suggested,
    }


def main():
    parser = argparse.ArgumentParser(description="Triage ticket scorer")
    parser.add_argument("--ticket", required=True, help="Path to ticket JSON file")
    parser.add_argument("--config", default=None, help="Path to knowledge/scorer/ directory")
    parser.add_argument("--log", default=None, help="Path to JSONL log file (appends one record per run)")
    parser.add_argument("--source", default="live", help="Record source tag: 'live' or 'testbed'")
    args = parser.parse_args()

    if args.config is None:
        args.config = Path(__file__).parent / "knowledge" / "scorer"

    graders_config, weights_config, components_config = load_config(args.config)

    with open(args.ticket) as f:
        issue = json.load(f)

    if "key" not in issue and "fields" not in issue:
        print(json.dumps({"error": "Invalid ticket format"}))
        sys.exit(1)

    result = score_ticket(issue, graders_config, weights_config, components_config)
    print(json.dumps(result, indent=2))

    if args.log:
        log_record = {
            "ticket": result["key"],
            "timestamp": result["timestamp"],
            "scorer_version": result["scorer_version"],
            "score": result["score"],
            "verdict": result["verdict"],
            "graders_fired": result["graders_fired"],
            "category_scores": {cat: info["score"] for cat, info in result["categories"].items()},
            "verdict_accepted": None,
            "corrections": [],
            "source": args.source,
        }
        log_path = Path(args.log)
        with open(log_path, "a") as f:
            f.write(json.dumps(log_record) + "\n")


if __name__ == "__main__":
    main()
