"""
Ecosystem Intelligence Node

This node extracts structured intelligence about the macro-environmental context,
institutional dynamics, competitive landscape, and systemic risks surrounding
 a subject-audience ecosystem.
"""

import asyncio
import os
import sys
from typing import Dict, Any

# Add the workspace root and RetrievalPipeline to the Python path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
RETRIVAL_PIPELINE_PATH = os.path.join(WORKSPACE_ROOT, "RetrievalPipeline")

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)
if RETRIVAL_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, RETRIVAL_PIPELINE_PATH)

from RetrievalPipeline.Graph.Nodes.GPT_ResearcherNode.ResearchNode import make_research
from RetrievalPipeline.Graph.Nodes.CompressionNode import (
    compress_intelligence_report,
    compress_subject_intelligence,
    format_compressed_for_injection,
)
from RetrievalPipeline.Graph.StateGraph import GraphState


def _resolve_report_path(report_path: str | None) -> str | None:
    """Resolve report path to absolute path if it exists."""
    if not report_path:
        return None
    if os.path.isabs(report_path) and os.path.exists(report_path):
        return report_path
    candidate = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", report_path)
    if os.path.exists(candidate):
        return candidate
    if os.path.exists(report_path):
        return report_path
    return None


def compress_intelligence_report(report_content: str, short_query: str, target_node: str = None) -> str:
    """Compress an intelligence report for injection into a specific downstream node."""
    state: GraphState = {
        "subject_intelligence_report": report_content,
        "user_initial_query": short_query,
    }
    compressed_state = compress_subject_intelligence(state)
    compressed = compressed_state.get("compressed_intelligence", {})
    if not compressed:
        return report_content[:8000]
    return format_compressed_for_injection(compressed, target_node=target_node)


def build_ecosystem_query(
    subject_name: str,
    subject_summary: str,
    audience_summary: str,
) -> str:
    """Build the research query for ecosystem intelligence."""
    
    macro_environmental_context_layer = {
        "name": "Macro Environmental Context Layer",
        "objective": (
            "Analyze broader political, socio-economic, religious, and institutional conditions "
            "that enable or hinder the Subject-Audience ecosystem."
        ),
        "extraction_tasks": [
            "Identify the national and regional political climate relevant to the Subject-Audience ecosystem, including governance stability, ideological currents, and state-society relations.",
            "Analyze socio-economic conditions (employment, inequality, urbanization, migration, education access) that shape audience receptivity and institutional tolerance.",
            "Map the religious or ideological landscape at the macro level — dominant schools, official religious policy, sectarian dynamics — and how they frame the ecosystem's operating space.",
            "Identify historical or structural conditions (conflicts, reforms, demographic shifts, media liberalization) that created the current environment.",
            "Distinguish enabling conditions (tolerance windows, platform access, institutional gaps) from constraining conditions (crackdowns, censorship regimes, economic pressure).",
            "Explain how macro conditions interact with the Subject's influence model and Audience composition without re-describing subject biography or audience segments.",
        ],
    }

    institutional_power_dynamics_layer = {
        "name": "Institutional Power Dynamics Layer",
        "objective": (
            "Map relationships with formal authorities, state institutions, official religious bodies, "
            "and legal/regulatory frameworks governing the Subject-Audience ecosystem."
        ),
        "extraction_tasks": [
            "Identify state institutions, ministries, security agencies, and regulatory bodies with documented authority over the subject's activities or audience.",
            "Map official religious institutions (fatwa councils, religious ministries, authorized preachers) and their documented stance toward the subject or rival authorities.",
            "Analyze legal and regulatory frameworks — licensing, blasphemy laws, media regulations, NGO rules — that constrain or protect the ecosystem.",
            "Document formal alliances, endorsements, warnings, investigations, arrests, or sanctions involving the subject or key ecosystem actors.",
            "Identify institutional gatekeepers (editors, platform liaisons, university administrators, mosque committees) who mediate access to audiences.",
            "Distinguish de jure institutional positions from de facto enforcement patterns when evidence supports the distinction.",
        ],
    }

    competitive_rivalry_landscape_layer = {
        "name": "Competitive Rivalry Landscape Layer",
        "objective": (
            "Analyze competing actors, rival movements, alternative authorities, and counter-ecosystems "
            "fighting for the same audience share or institutional legitimacy."
        ),
        "extraction_tasks": [
            "Identify principal rival influencers, movements, or schools of thought competing for the same audience segments.",
            "Map institutional rivals — competing religious councils, political factions, media networks — and their documented conflicts with the subject's ecosystem.",
            "Analyze counter-ecosystems (state-aligned networks, reformist currents, extremist fringe groups) that actively oppose or absorb the subject's audience.",
            "Document specific rivalry events: public debates, fatwa wars, platform battles, institutional exclusions, or audience poaching incidents.",
            "Explain how rivals frame the subject and how the subject's ecosystem frames rivals, citing specific documented exchanges.",
            "Identify structural advantages or disadvantages the subject's ecosystem holds relative to competitors without repeating audience psychology analysis.",
        ],
    }

    media_algorithmic_infrastructure_layer = {
        "name": "Media & Algorithmic Infrastructure Layer",
        "objective": (
            "Analyze the physical and digital platform infrastructure and how censorship, "
            "algorithmic distribution, or offline networks impact ecosystem viability."
        ),
        "extraction_tasks": [
            "Inventory the primary distribution channels (Telegram, YouTube, Facebook, satellite TV, podcasts, books, mosques, conferences) with evidence of actual usage.",
            "Analyze platform-specific constraints: content moderation, account bans, demonetization, shadow-banning, or algorithmic suppression documented for this ecosystem.",
            "Map offline infrastructure — study circles, mosque networks, publishing houses, travel circuits — that sustains the ecosystem beyond digital platforms.",
            "Identify state or corporate media infrastructure that amplifies or suppresses the subject's reach.",
            "Document infrastructure dependencies and redundancies: what happens when a primary channel is lost, based on historical evidence.",
            "Analyze how platform architecture (group chats vs. broadcast, recommendation engines vs. direct links) shapes reach without re-analyzing audience engagement psychology.",
        ],
    }

    systemic_risk_vulnerability_layer = {
        "name": "Systemic Risk & Vulnerability Layer",
        "objective": (
            "Identify structural vulnerabilities, single-points-of-failure, and systemic resilience "
            "within the Subject-Audience ecosystem."
        ),
        "extraction_tasks": [
            "Identify single-points-of-failure: subject dependency, platform concentration, geographic concentration, or institutional bottlenecks.",
            "Document historical stress events (arrests, bans, controversies, platform removals) and how the ecosystem responded based on evidence.",
            "Analyze systemic resilience mechanisms: decentralized networks, successor figures, archive preservation, cross-border relocation, institutional backing.",
            "Identify legal, financial, or reputational vulnerabilities with documented precedent in similar cases or this subject's history.",
            "Map cascading failure risks: how loss of one node (subject, platform, patron institution) would affect the broader ecosystem structure.",
            "Distinguish observed resilience from assumed resilience; mark unsupported resilience claims as [INSUFFICIENT EVIDENCE].",
        ],
    }

    institutional_macro_environment_layer = {
        "name": "Institutional Macro Environment Layer",
        "objective": (
            "Map real-world institutional responses, policy/legal impacts, and macro-level ripple effects "
            "based strictly on documented evidence — not speculation or prediction."
        ),
        "extraction_tasks": [
            "Document specific institutional responses to the subject or ecosystem: official statements, investigations, licensing actions, media campaigns, diplomatic notes.",
            "Map policy or legal changes that directly affected or were triggered by the subject's activities, citing primary government, judicial, or institutional sources.",
            "Identify macro-level ripple effects: how the ecosystem influenced public discourse, institutional debates, or cross-border reactions when evidence exists.",
            "Document institutional adaptation patterns: how state media, rival clerics, or regulatory bodies adjusted their posture over time based on observable actions.",
            "Record documented international or regional institutional reactions (foreign ministries, transnational religious bodies, diaspora institutions) when relevant.",
            "Do NOT generate hypothetical IF-THEN scenarios, future predictions, or simulation rules. Report only documented institutional behavior and its observed consequences.",
        ],
    }

    ECOSYSTEM_LAYERS = [
        macro_environmental_context_layer,
        institutional_power_dynamics_layer,
        competitive_rivalry_landscape_layer,
        media_algorithmic_infrastructure_layer,
        systemic_risk_vulnerability_layer,
        institutional_macro_environment_layer,
    ]

    lines = [
        "You are a Senior Systemic Intelligence Architect and Macro-Environmental Analyst.",
        "You specialize in institutional dynamics, geopolitical context, competitive landscapes,",
        "regulatory frameworks, and structural ecosystem analysis.",
        "",
        "Your task is to produce a high-quality Macro Ecosystem Intelligence Report",
        "that can be used for downstream analysis and knowledge extraction.",
        "",
        "TASK: Macro Ecosystem & Structural Dynamics Profile",
        "",
        f"Subject: {subject_name}",
        "",
        "GROUNDING INSTRUCTION:",
        "Do NOT repeat subject biography or basic audience segmentation.",
        "Synthesize how the Subject + Audience entity operates INSIDE the broader macro ecosystem.",
        "Build strictly on the compressed Subject and Audience intelligence provided below.",
        "",
        "<subject_context>",
        subject_summary.strip(),
        "</subject_context>",
        "",
        "<audience_context>",
        audience_summary.strip(),
        "</audience_context>",
        "",
        "OBJECTIVE:",
        "Analyze the macro environment, institutional interactions, geopolitical and socio-religious landscape,",
        "competitive forces, and regulatory/media dynamics surrounding the Subject-Audience entity.",
        "Extract structured, evidence-based knowledge about how external structural forces shape this ecosystem.",
        "",
        "This is NOT a biography of the subject and NOT an audience profile.",
        "The macro structural environment is the primary object of analysis.",
        "",
        "CRITICAL CONSTRAINTS:",
        "- Documented evidence only. No predictions, no IF-THEN rules, no simulation parameters.",
        "- No invented statistics, percentages, or numerical metrics without direct citation.",
        "- Do not re-analyze subject ideology or audience psychology — synthesize macro structural dynamics.",
        "",
        "<macro_frameworks>",
    ]

    for layer in ECOSYSTEM_LAYERS:
        lines.append(f"### {layer['name']} ###")
        lines.append(f"Objective: {layer['objective']}")
        for task in layer["extraction_tasks"]:
            lines.append(f"- {task}")
        lines.append("")

    lines.append("</macro_frameworks>")

    return "\n".join(lines)


shared_guidelines = [
    "Collect evidence from multiple independent sources before drawing any conclusion. "
    "A minimum of three independent sources is required before treating any claim as established.",

    "Every factual claim must be traceable to a specific source. "
    "If a source cannot be identified, mark the claim explicitly as [UNVERIFIED] and do not present it as fact.",

    "Direct quotations require a direct URL or document reference to the exact source. "
    "If the original text or recording cannot be located, do not quote — paraphrase with source attribution instead.",

    "Explicitly mark the epistemic status of every major claim using one of: "
    "[VERIFIED], [STRONG EVIDENCE], [REASONABLE INFERENCE], or [INSUFFICIENT EVIDENCE]. "
    "Never present inference as verified fact.",

    "When two or more sources conflict on any fact, present all versions explicitly, "
    "identify each source, and flag the conflict. Never silently resolve a conflict by choosing one version.",

    "Do not omit a section because information is unavailable. "
    "Instead write: 'Insufficient reliable evidence found on this topic.' "
    "Visible gaps are more valuable than silent omissions.",

    "Prioritize structured knowledge extraction over narrative writing. "
    "The output should read as an intelligence document, not a biography or an essay.",

    "Avoid repeating the same information across multiple sections. "
    "Each section must contribute new knowledge. "
    "If a point was already established, reference it — do not restate it.",

    "Produce findings grounded strictly in empirical evidence that support downstream intelligence analysis and knowledge graph construction.",

    "IMPORTANT: This report will be ingested directly into a Retrieval-Augmented Generation (RAG) knowledge base. Every unnecessary sentence reduces retrieval quality.",

    "Start immediately with the first requested section heading. Never write an introduction, overview, executive summary, preface, opening paragraph, or any contextual lead-in.",

    "Do not generate any conclusion, closing remarks, summary, final thoughts, recommendations, or wrap-up section under any circumstance.",

    "The report must end immediately after the final requested section. Do not append any closing sentence or transition.",

    "Output only the explicitly requested sections in the specified order. Do not create additional headings or explanatory sections.",

    "CRITICAL RULE: Do not generate, estimate, or invent any percentage, statistic, or numerical figure unless explicitly stated in a directly cited source. A number without a direct citation is a hallucination.",

    "Do not generate simulation rules, pseudocode, IF-THEN statements, agent behaviors, predictive models, or hypothetical scenarios.",
]


ecosystem_guidelines = shared_guidelines + [
    "This agent analyzes the MACRO ENVIRONMENT in which the Subject-Audience entity operates. "
    "Focus on institutional interactions, geopolitical context, competitive forces, regulatory dynamics, "
    "and structural ecosystem conditions — not subject biography or audience psychology.",

    "Do NOT repeat subject biography, personal ideology analysis, or basic audience segmentation. "
    "Those were covered by the Subject and Audience Intelligence runs. "
    "Synthesize how the Subject + Audience entity operates INSIDE the broader macro ecosystem.",

    "Treat the Subject-Audience pair as a single influence entity embedded in a macro structural environment. "
    "The subject is an influence node; the audience is a mobilized constituency — "
    "but your analysis target is the external environment they inhabit.",

    "Zero speculation: do not predict future events, generate IF-THEN rules, or propose hypothetical scenarios. "
    "Report only documented institutional behavior, observable structural dynamics, and evidence-backed macro patterns.",

    "Multi-source verification is mandatory for institutional claims. "
    "Government statements, legal records, official religious rulings, and reputable journalism "
    "should corroborate major claims about institutional posture.",

    "When analyzing rivals and competitors, focus on structural and institutional competition "
    "for audience share and legitimacy — not on re-describing audience motivations.",

    "When analyzing media infrastructure, focus on platform viability, censorship, and distribution mechanics — "
    "not on re-describing how audiences engage with content.",

    "If the model drifts into subject biography, audience psychology, or abstract political philosophy, "
    "stop and refocus on macro-structural and institutional dynamics only.",

    "Do not present findings as a formal empirical study, survey, or quantitative proof "
    "unless the evidence clearly supports that framing.",
]


async def run_ecosystem_intelligence(
    state: GraphState,
    max_sections: int = 6,
) -> GraphState:
    """
    Run ecosystem intelligence analysis.
    
    Args:
        state: The current graph state
        subject_name: Name of the subject to analyze
        subject_intelligence_path: Path to subject intelligence report
        audience_intelligence_path: Path to audience intelligence report
        max_sections: Maximum number of sections to generate
        
    Returns:
        Updated GraphState with ecosystem intelligence results
    """
    # Extract required data from state
    subject_name = state.get("user_initial_query")
    if not subject_name:
        raise ValueError("user_initial_query must be provided in state")
    
    # Get reports from state.reports
    reports = state.get("reports", {})
    subject_report = reports.get("subject", {}).get("content", "")
    audience_report = reports.get("audience", {}).get("content", "")
    
    # If reports are not available, check for paths in input_paths
    input_paths = state.get("input_paths", {})
    if not subject_report:
        subject_path = input_paths.get("subject_intelligence_path")
        if not subject_path:
            raise ValueError("Either subject report in state.reports or subject_intelligence_path must be provided")
        
        if not os.path.exists(subject_path):
            raise FileNotFoundError(f"Subject intelligence report not found: {subject_path}")
        
        with open(subject_path, "r", encoding="utf-8") as f:
            subject_report = f.read()
    
    if not audience_report:
        audience_path = input_paths.get("audience_intelligence_path")
        if not audience_path:
            raise ValueError("Either audience report in state.reports or audience_intelligence_path must be provided")
        
        if not os.path.exists(audience_path):
            raise FileNotFoundError(f"Audience intelligence report not found: {audience_path}")
        
        with open(audience_path, "r", encoding="utf-8") as f:
            audience_report = f.read()
    
    # Load environment and MCP configs
    try:
        from RetrievalPipeline.Graph.Chains.tests.mcp_config import build_audience_mcp_configs, load_environment
    except ImportError:
        # Fallback for when running from node directory
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "Chains", "tests"))
        from mcp_config import build_audience_mcp_configs, load_environment
    
    load_environment()
    mcp_configs = build_audience_mcp_configs()

    # Compress reports (consumer-aware: target the ecosystem node with provenance + gaps)
    subject_summary = compress_intelligence_report(subject_report, subject_name, target_node="ecosystem")
    audience_summary = compress_intelligence_report(audience_report, subject_name, target_node="ecosystem")

    # Build ecosystem query
    full_query = build_ecosystem_query(subject_name, subject_summary, audience_summary)

    # Load environment and MCP configs
    try:
        from RetrievalPipeline.Graph.Chains.tests.mcp_config import build_audience_mcp_configs, load_environment
    except ImportError:
        # Fallback for when running from node directory
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "Chains", "tests"))
        from mcp_config import build_audience_mcp_configs, load_environment
    
    load_environment()
    mcp_configs = state.get("mcp_configs", build_audience_mcp_configs())
    mcp_strategy = state.get("mcp_strategy", "fast")
    
    # Prepare the state for research
    research_state: GraphState = {
        **state,  # Preserve existing state
        "chain_input": {
            "query": full_query,
            "guidelines": ecosystem_guidelines,
            "follow_guidelines": True,
            "max_sections": max_sections,
            "verbose": True,
            "prompt_type": "ecosystem",
            "mcp_configs": mcp_configs,
        },
        "prompt_type": "ecosystem",
        "mcp_strategy": mcp_strategy,
        "identity_data": {
            "needs_reprocessing": False,
            "feedback_notes": ""
        },
        "research_iteration": state.get("research_iteration", 0),
    }

    print("⏳ Running Ecosystem Intelligence Agent...")
    result = await make_research(research_state)

    # Extract results
    candidates = result.get("profile_candidates", [])
    candidate = candidates[0] if candidates else {}
    report = candidate.get("full_report", "")
    sources = candidate.get("sources", [])
    costs = candidate.get("costs", 0.0)
    
    # Store the result in state.reports
    if report:
        reports = state.get("reports", {})
        reports["ecosystem"] = {
            "content": report,
            "path": f"{subject_name}_ecosystem_intelligence.md",
            "sources": sources,
            "costs": costs,
            "metadata": {
                "subject_name": subject_name,
                "max_sections": max_sections,
                "report_length": len(report),
                "prompt_type": "ecosystem"
            }
        }
        
        # Save to file
        output_path = reports["ecosystem"]["path"]
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"✅ Ecosystem intelligence report generated: {output_path}")
        print(f"   Length : {len(report)} chars")
        print(f"   Sources: {len(sources)}")
        print(f"   Costs  : {costs}")
    
    # Update state with results
    updated_state = {
        **state,
        **result,
        "reports": reports,
        "prompt_type": "ecosystem"
    }
    
    return updated_state


