"""
Audience Intelligence Node

This node extracts structured intelligence about a subject's audience ecosystem,
including segmentation, motivations, community dynamics, and behavioral impact.
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
    compress_reference_doc,
    format_compressed_for_injection,
    get_or_compress,
)
from RetrievalPipeline.Graph.StateGraph import GraphState


async def summarize_briefings(briefing_1_path: str, briefing_2_path: str, short_query: str) -> str:
    """Combine and compress two briefing documents."""
    
    with open(briefing_1_path, "r", encoding="utf-8") as f:
        briefing_1 = f.read()
    
    with open(briefing_2_path, "r", encoding="utf-8") as f:
        briefing_2 = f.read()
    
    combined_report = (
        "SOURCE 1:\n" + briefing_1.strip() + "\n\n"
        "SOURCE 2:\n" + briefing_2.strip()
    )

    if len(combined_report) <= 8000:
        return combined_report

    return compress_reference_doc(combined_report)


async def summarize_single_profile(profile_path: str, short_query: str) -> str:
    """Compress a single profile document if it's too long."""
    
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_content = f.read()

    if len(profile_content) <= 8000:
        return profile_content

    return compress_reference_doc(profile_content)
    
    return summary


def build_audience_query(subject_name: str, subject_profile: str, combined_summary: str, subject_briefing: str = "") -> str:
    """Build the research query for audience intelligence."""
    
    audience_profile_layer = {
        "name": "Audience Profile Layer",
        "objective": "Identify who composes the audience, the major segments around the subject, and how demographic and digital engagement patterns distinguish them.",
        "extraction_tasks": [
            "Identify the major audience segments supported by available evidence.",
            "Characterize segments by age, gender, education, profession, geography, socioeconomic background, digital behavior, and online engagement.",
            "Identify recurring ideological, religious, cultural, or social characteristics when evidence supports them.",
            "Distinguish core followers, regular consumers, casual audiences, critics, and former followers whenever possible.",
            "Identify which audience segments are most engaged across platforms and communication channels.",
            "Identify recurring roles assumed by audience members (e.g., students, activists, professionals, content creators, community leaders).",
            "Describe observable differences between segments instead of treating the audience as a homogeneous group."
        ]
    }

    audience_motivation_layer = {
        "name": "Audience Motivation Layer",
        "objective": "Understand why different audience groups are attracted to the subject and which needs, identities, or social dynamics the ecosystem appears to satisfy.",
        "extraction_tasks": [
            "Identify the primary motivations attracting each audience segment.",
            "Analyze religious, ideological, psychological, educational, political, cultural, social, or practical motivations when supported by evidence.",
            "Identify recurring fears, aspirations, frustrations, identity needs, or perceived problems that increase engagement.",
            "Explain which aspects of the subject's communication resonate with different audience groups.",
            "Distinguish motivations that attract new audiences from those that sustain long-term engagement.",
            "Identify observable factors that strengthen trust, loyalty, or continued participation.",
            "Identify factors that reduce engagement, create disagreement, or lead people to disengage."
        ]
    }

    community_ecosystem_layer = {
        "name": "Community & Ecosystem Layer",
        "objective": "Map how the audience organizes into communities, networks, and ecosystems around the subject.",
        "extraction_tasks": [
            "Identify the major communities, networks, or ecosystems surrounding the subject.",
            "Identify formal and informal community structures when evidence exists.",
            "Identify influential followers, secondary influencers, organizations, institutions, or media channels that shape the ecosystem.",
            "Identify recurring community norms, identity markers, values, terminology, and shared narratives.",
            "Analyze how newcomers become integrated into the community.",
            "Identify internal divisions, subgroups, or competing interpretations when they exist.",
            "Explain how different parts of the ecosystem interact, reinforce each other, and connect across online and offline spaces."
        ]
    }

    behavioral_impact_layer = {
        "name": "Behavioral Impact Layer",
        "objective": "Identify how exposure to the subject influences audience beliefs, decisions, behaviors, and social interactions.",
        "extraction_tasks": [
            "Identify observable changes in beliefs, values, priorities, attitudes, identity, or practices associated with exposure to the subject.",
            "Analyze behavioral effects in religion, politics, education, family life, social relationships, civic participation, or other relevant domains.",
            "Distinguish immediate reactions from longer-term behavioral changes.",
            "Identify which audience segments are most influenced by different aspects of the subject's discourse.",
            "Identify intended and unintended behavioral outcomes when evidence exists.",
            "Identify positive, negative, and mixed outcomes without assuming the direction of the impact.",
            "Explain the mechanisms linking the subject's communication to observed behavioral change."
        ]
    }

    social_cultural_impact_layer = {
        "name": "Social & Cultural Impact Layer",
        "objective": "Assess the broader social, cultural, educational, political, and institutional effects associated with the subject's audience ecosystem.",
        "extraction_tasks": [
            "Identify observable social, cultural, educational, political, religious, or institutional impacts supported by evidence.",
            "Distinguish effects at the individual, community, and broader societal levels.",
            "Identify changes in public discourse, norms, or collective behavior associated with the ecosystem.",
            "Identify positive, negative, and mixed societal outcomes without assuming the direction of the impact.",
            "Explain which audience segments or communities are most affected by different aspects of the subject's ideas.",
            "Identify long-term societal trends or recurring patterns when evidence exists.",
            "Separate direct observable impact from indirect or inferred effects."
        ]
    }

    diffusion_recruitment_layer = {
        "name": "Diffusion & Recruitment Layer",
        "objective": "Understand how ideas spread, how new audiences enter the ecosystem, and how influence expands over time.",
        "extraction_tasks": [
            "Identify the primary channels through which new audiences discover the subject.",
            "Analyze how ideas spread across platforms, communities, institutions, and personal networks.",
            "Identify recurring recruitment pathways into the ecosystem when evidence exists.",
            "Explain how casual consumers become regular followers and then active advocates or secondary influencers.",
            "Identify feedback loops that reinforce audience growth and idea diffusion.",
            "Identify barriers that slow, weaken, or prevent diffusion.",
            "Explain why certain ideas spread more successfully than others."
        ]
    }

    trust_persuasion_layer = {
        "name": "Trust & Persuasion Mechanisms Layer",
        "objective": "Reverse engineer how trust is built, maintained, and translated into persuasion across different audience segments.",
        "extraction_tasks": [
            "Identify the primary factors that lead different audience segments to trust the subject.",
            "Analyze how credibility, authority, authenticity, and legitimacy are established and reinforced.",
            "Identify recurring persuasive strategies, emotional appeals, framing techniques, and authority signals.",
            "Explain how different audience segments evaluate competing sources of information.",
            "Identify recurring psychological, social, cultural, or religious mechanisms that strengthen commitment to the subject's ideas.",
            "Identify factors that weaken trust, reduce influence, or lead followers to disengage.",
            "Separate evidence-supported mechanisms from inference."
        ]
    }

    opposition_resistance_layer = {
        "name": "Opposition & Resistance Layer",
        "objective": "Understand how individuals and communities reject, resist, reinterpret, or oppose the subject's ideas.",
        "extraction_tasks": [
            "Identify principal critics, competing communities, institutions, or alternative schools of thought.",
            "Analyze the primary reasons different groups reject or criticize the subject.",
            "Identify recurring counter-narratives, competing interpretations, and ideological disagreements.",
            "Explain how supporters, critics, and neutral observers interpret the same events differently.",
            "Identify audience segments that are resistant to the subject's influence and explain why.",
            "Analyze factors that reduce susceptibility to the subject's discourse.",
            "Identify recurring conflicts, polarization patterns, and interaction dynamics between supporters and opponents."
        ]
    }

    audience_simulation_layer = {
        "name": "Audience Knowledge Extraction Layer",
        "objective": "Capture observable audience patterns and evidence without inventing numeric estimates, predictions, or behavioral simulations.",
        "extraction_tasks": [
            "Identify the major audience entities, groups, and recurring roles within the ecosystem.",
            "Extract stable characteristics, identities, values, motivations, and behavioral tendencies associated with each audience segment.",
            "Identify observable patterns in engagement, trust, participation, influence, and disengagement.",
            "When a pattern is reported, attach the specific supporting data or source evidence that showed it.",
            "Do not invent counts, percentages, rankings, or numerical scores unless they are explicitly present in the evidence.",
            "Extract recurring relationships between audience segments, communities, organizations, institutions, platforms, and influential individuals.",
            "Identify recurring mechanisms through which information spreads, trust develops, influence is maintained, communities organize, and behavioral change occurs.",
            "Extract recurring conditions, contextual factors, and observable triggers associated with changes in audience behavior when supported by evidence.",
            "Identify recurring patterns, dependencies, and causal mechanisms explicitly supported by evidence while clearly separating observation from inference.",
            "Organize findings into reusable structured knowledge without generating simulations, behavioral rules, or predictions."
        ]
    }

    layers = [
        audience_profile_layer,
        audience_motivation_layer,
        community_ecosystem_layer,
        behavioral_impact_layer,
        social_cultural_impact_layer,
        diffusion_recruitment_layer,
        trust_persuasion_layer,
        opposition_resistance_layer,
        audience_simulation_layer,
    ]

    lines = [
        "You are an expert researcher specializing in audience ecosystems,",
        "social influence, collective behavior, community analysis,",
        "diffusion dynamics, and socio-cultural systems.",
        "",
        "You analyze how audiences form, evolve, organize themselves,",
        "interpret ideas, respond to public figures,",
        "and influence one another across diverse cultural, political,",
        "religious, educational, and media environments.",
        "",
        "Your task is to produce a high-quality Audience Intelligence Report",
        "that can support downstream intelligence analysis,",
        "",
        "TASK: Audience Intelligence Profile",
        "",
        f"Subject: {subject_name}",
        "",
        "=== SUBJECT PROFILE CONTEXT ===",
        subject_profile.strip(),
        "===============================",
        "",
        "=== COMBINED SUBJECT INTELLIGENCE SUMMARY ===",
        combined_summary.strip(),
        "=============================================",
        "",
        "=== SUBJECT INTELLIGENCE BRIEFING (audience-targeted, pre-compressed) ===",
        subject_briefing.strip() if subject_briefing else "(none provided)",
        "========================================================================",
        "",
        "OBJECTIVE:",
        "Reverse engineer the audience ecosystem surrounding the subject.",
        "",
        "Treat the subject as the source of influence rather than the primary object of analysis.",
        "Identify who composes the audience, why they are attracted to the subject, and how age groups and online engagement shape attraction, retention, and sharing behavior.",
        "Describe how audience members interact with content, how it influences their personal networks, and how specific segments respond differently.",
        "Explain how ideas spread, how trust forms, how beliefs evolve, and how groups support, reinterpret, criticize, or resist the subject.",
        "",
        "Pay particular attention to age cohorts, platform-specific behavior, digital interaction patterns, and demographic characteristics that distinguish segments.",
        "Treat audience behavior, community activity, and documented interactions as the primary evidence, not the subject's own claims alone.",
        "Capture observable audience behavior, evidence-based knowledge about audience structures, relationships, mechanisms, behavioral patterns, and ecosystem dynamics.",
        "Build upon the Subject Intelligence Summary rather than repeating it.",
        "Do not generate simulation rules, agent behaviors, or hypothetical audience models.",
        "Give much lower priority to funding or financial sources unless they directly explain audience attraction or behavior.",
        "Focus on mechanisms, relationships, observable behaviors, and recurring patterns instead of narrative summaries.",
        "",
        "⚠️ CRITICAL:",
        "",
        "This investigation is limited to observable evidence.",
        "",
        "Do not generate predictions.",
        "Do not simulate behavior.",
        "Do not invent motivations.",
        "Do not infer hidden psychological states without sufficient evidence.",
        "Do not generate IF-THEN rules or agent behaviors.",
        "",
        "Document the ecosystem as it exists.",
        "",
        "RESEARCH FRAMEWORKS:",
        "",
    ]

    for layer in layers:
        lines.append(f"### {layer['name']} ###")
        lines.append(f"Objective: {layer['objective']}")
        for task in layer["extraction_tasks"]:
            lines.append(f"- {task}")
        lines.append("")

    return "\n".join(lines)


shared_guidelines = [
    "Use additional languages Search for sources beyond English when they are relevant to the subject's communication, audience, or cultural context.",

    "Collect evidence from multiple independent sources before drawing any conclusion. "
    "Major factual or analytical claims should normally be corroborated by multiple independent sources.",

    "Every factual claim must be traceable to a specific source. "
    "If a source cannot be identified, mark the claim explicitly as [UNVERIFIED] and do not present it as fact.",

    "If the original text or recording cannot be located, do not quote — paraphrase with source attribution instead.",

    "Separate the subject's own stated positions from descriptions, labels, or accusations "
    "made by supporters, critics, media outlets, or third parties. "
    "Never present external characterizations as established facts about the subject.",

    "When attributing specific opinions, fatwas, theories, or positions to the subject, "
    "verify that they were explicitly expressed by the subject in a reliable source. "
    "Do not attribute claims based solely on quotations by third parties, social media posts, or unsourced compilations.",

    "If a particular event or statement appears more than twice across different sections, "
    "this is a signal of over-reliance. Actively seek additional independent examples "
    "to represent the same pattern before continuing.",

    # ============================================================
    # INFERENCE vs FACT
    # ============================================================
    "Separate verified evidence from analytical inference. "
    "Never present inference as established fact.",

    "Audience demographics, motivations, and psychological profiles are usually inferred. "
    "Clearly distinguish such inferences from directly observed evidence and explain the observations supporting them.",

    # ============================================================
    # SOURCE QUALITY
    # ============================================================
    "Collect the largest possible body of evidence that explains who the audience is and how they engage with the subject in depth.",

    # ============================================================
    # CONFLICTS & GAPS
    # ============================================================
    "When two or more sources conflict on any fact, present all versions explicitly, "
    "identify each source, and describe the disagreement instead of silently choosing one version.",

    # ============================================================
    # OUTPUT DISCIPLINE
    # ============================================================
    "Prioritize structured knowledge extraction over descriptive writing. "
    "The output should read as an intelligence report rather than a biography or essay.",

    "Avoid repeating the same information across multiple sections. "
    "Each section should contribute new analytical knowledge. "
    "Reference previously established findings instead of restating them.",

    "Produce reusable analytical knowledge that can support downstream intelligence analysis, "
]


audience_guidelines = shared_guidelines + [
    "Focus on the audience ecosystem surrounding the subject, not the subject themselves. Treat the subject as the source of influence rather than the primary object of analysis.",
    "The primary objective is to understand the subject's audience: who they are, why they are attracted to the subject, how they interpret the subject's message, how they engage online, and how psychological, social, cultural, and ideological factors shape them.",
    "Prioritize audience composition, segmentation, motivations, psychological tendencies, behavioral patterns, engagement styles, values, identities, social backgrounds, online communities, and relationships with the subject.",
    "Identify distinct audience segments and classify them with precise age, geographic/cultural background, education/intellectual profile, ideological tendencies, and observed digital behavior.",
    "Treat audience psychology as a first-class analytical target. Analyze emotional drivers, cognitive frames, trust mechanisms, authority perceptions, community norms, and platform-specific behavior using evidence.",
    "Give much lower priority to funding or financial sources unless they directly explain audience attraction or behavior. Do not treat financial details as a primary topic.",
    "Do not generate simulation rules, agent behaviors, hypothetical audience models, predictions, or abstract frameworks that are not grounded in documented audience evidence.",
    "Do not frame the work as an empirical study, survey, or quantitative analysis unless the evidence explicitly supports that framing. Prefer qualitative description of phenomena in ordinary language.",
    "If a pattern, tendency, or phenomenon is not clearly measured or strongly supported by evidence, describe it as a recurring pattern, observable tendency, or cautious qualitative observation rather than as a statistically established fact.",
    "Avoid unsupported numbers, percentages, rankings, scores, or fabricated metrics. When evidence is incomplete or uncertain, use cautious wording such as 'appears', 'seems', 'is often described as', or 'is commonly associated with'.",
    "List the exact source or data point behind each observed pattern, and attach it to the finding.",
    "If numeric values are uncertain, prioritize qualitative/descriptive language (e.g., 'many', 'some', 'a minority') and explicitly state uncertainty. Do not fabricate counts, percentages, rankings, or numerical estimates without clear supporting evidence.",

    "Search for evidence about audience composition, behavior, and impact. Primary sources include audience comments, forum discussions, social media interactions, survey data, community content, and documented audience activities.",
    "Use the subject's own content mainly to understand what attracts audiences, not as direct evidence about the audiences themselves.",
    "When analyzing motivations and behaviors, draw examples from multiple platforms, time periods, and audience groups. Do not rely on the same example more than once across different sections.",

    "Do not assume that high-quality evidence must come solely from peer-reviewed academic papers. The main aim is to collect credible, traceable data points, while avoiding tabloid, sensational, or clearly biased sources.",
    "For many subjects, the most valuable evidence often comes from primary materials, official documents, interviews, books, archived webpages, speeches, legal records, government publications, reputable journalism, NGO reports, and other verifiable documentary sources.",
    "Select sources based on relevance, credibility, traceability, and evidential value—not on whether they are academic publications.",
]


async def run_audience_intelligence(
    state: GraphState,
    max_sections: int = 12,
) -> GraphState:
    """
    Run audience intelligence analysis.
    
    Args:
        state: The current graph state
        subject_name: Name of the subject to analyze
        profile_path: Path to subject profile document
        briefing_1_path: Path to first briefing document
        briefing_2_path: Path to second briefing document
        max_sections: Maximum number of sections to generate
        
    Returns:
        Updated GraphState with audience intelligence results
    """
    # Extract required data from state
    subject_name = state.get("user_initial_query")
    if not subject_name:
        raise ValueError("user_initial_query must be provided in state")
    
    # Get summaries from state.reports
    reports = state.get("reports", {})
    profile_summary = reports.get("profile_summary", {}).get("content", "")
    briefing_summary = reports.get("briefing_summary", {}).get("content", "")
    
    # If summaries are not available, we'll need to check input_paths
    input_paths = state.get("input_paths", {})
    if not profile_summary:
        profile_path = input_paths.get("subject_profile_path")
        if not profile_path:
            raise ValueError("Either profile_summary or subject_profile_path must be provided in state")
        
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Profile not found: {profile_path}")
        
        with open(profile_path, "r", encoding="utf-8") as f:
            profile_summary = f.read()
    
    if not briefing_summary:
        briefing_1_path = input_paths.get("briefing_1_path")
        briefing_2_path = input_paths.get("briefing_2_path", briefing_1_path)
        
        if not briefing_1_path:
            raise ValueError("Either briefing_summary or briefing_1_path must be provided in state")
        
        if not os.path.exists(briefing_1_path):
            raise FileNotFoundError(f"Briefing 1 not found: {briefing_1_path}")
        
        if not os.path.exists(briefing_2_path):
            raise FileNotFoundError(f"Briefing 2 not found: {briefing_2_path}")
        
        # Read and combine briefings
        with open(briefing_1_path, "r", encoding="utf-8") as f:
            briefing_1 = f.read()
        
        with open(briefing_2_path, "r", encoding="utf-8") as f:
            briefing_2 = f.read()
        
        combined_report = (
            "SOURCE 1:\n" + briefing_1.strip() + "\n\n"
            "SOURCE 2:\n" + briefing_2.strip()
        )
        
        # Compress the combined briefings with the reference-doc compressor
        # (appropriate for briefings; short-circuits when content is small).
        briefing_summary = compress_reference_doc(combined_report)
    
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

    # Pre-compress the upstream SUBJECT report into an audience-targeted briefing (provenance + gaps).
    subject_report_content = state.get("reports", {}).get("subject", {}).get("content", "")
    subject_briefing = ""
    if subject_report_content:
        sub_compressed = get_or_compress(state, "subject", target_node="audience")
        subject_briefing = format_compressed_for_injection(
            sub_compressed.get("compressed_intelligence", sub_compressed),
            target_node="audience",
        )

    # Build audience query from the resolved profile + briefing summaries + subject briefing
    full_query = build_audience_query(subject_name, profile_summary, briefing_summary, subject_briefing)
    
    # Prepare the state for research
    research_state: GraphState = {
        **state,  # Preserve existing state
        "chain_input": {
            "query": full_query,
            "guidelines": audience_guidelines,
            "follow_guidelines": True,
            "max_sections": max_sections,
            "verbose": True,
            "prompt_type": "audience",
            "mcp_configs": mcp_configs,
            "mcp_strategy": mcp_strategy,
        },
        "prompt_type": "audience",
        "mcp_strategy": mcp_strategy,
        "identity_data": {
            "needs_reprocessing": False,
            "feedback_notes": ""
        },
        "research_iteration": state.get("research_iteration", 0),
    }

    print("⏳ Running Audience Intelligence Agent...")
    print(f"   📄 Profile: {len(profile_summary)} chars")
    print(f"   📄 Combined Summary: {len(briefing_summary)} chars")
    
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
        reports["audience"] = {
            "content": report,
            "path": f"{subject_name}_audience_intelligence.md",
            "sources": sources,
            "costs": costs,
            "metadata": {
                "subject_name": subject_name,
                "max_sections": max_sections,
                "report_length": len(report),
                "prompt_type": "audience"
            }
        }
        
        # Save to file
        output_path = reports["audience"]["path"]
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"✅ Audience intelligence report generated: {output_path}")
        print(f"   Length : {len(report)} chars")
        print(f"   Sources: {len(sources)}")
        print(f"   Costs  : {costs}")
    
    # Update state with results
    updated_state = {
        **state,
        **result,
        "reports": reports,
        "prompt_type": "audience"
    }
    
    return updated_state


