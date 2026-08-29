# audience_intelligence_agent.py

import asyncio
import os
import sys
from Nodes.GPT_ResearcherNode.ResearchNode import make_research
from StateGraph import GraphState
from Nodes.CompressionNode.research_compressor_node import (
    compress_subject_intelligence,
    format_compressed_for_injection,
)
# Make the local tests folder importable whether this file is run as a script
# or imported as part of a package.
TESTS_DIR = os.path.dirname(__file__)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

try:
    from .mcp_config import build_audience_mcp_configs, load_environment
except ImportError:
    from mcp_config import build_audience_mcp_configs, load_environment

load_environment()

# Ensure the research process keeps direct Tavily search active by default
# while also allowing MCP servers to participate.
os.environ.setdefault("RETRIEVER", "tavily,mcp")

mcp_configs = build_audience_mcp_configs()

# ============================================================
# LAYERS - AUDIENCE ECOSYSTEM
# ============================================================

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

# PRIMARY ANALYTICAL OBJECTIVE
primary_analytical_objective = [
    "The primary objective of this research is not to build a theoretical, philosophical, or epistemological understanding of the subject.",
    "The primary objective is to understand the subject's audience: who they are, why they are attracted to the subject, how they interpret the subject's message, how they interact with it, and what psychological, social, cultural, and ideological factors characterize them.",
    "The audience is the principal object of analysis.",
    "The subject should be analyzed mainly as the source of influence that shapes the audience rather than as the final object of interest.",
    "Unless explicitly instructed otherwise, the majority of the final report should focus on the audience ecosystem rather than the subject's biography, intellectual history, or ideas in isolation.",
    "Prioritize understanding audience composition, segmentation, motivations, psychological tendencies, behavioral patterns, engagement styles, values, identities, social backgrounds, online communities, and relationships with the subject over producing an exhaustive description of the subject's own views.",
    "Identify and analyze distinct audience segments separately whenever evidence allows.",
    "Different groups often follow the same subject for different reasons; avoid treating the audience as a homogeneous population.",
    "For each major audience segment, explain whenever possible: demographic tendencies, ideological orientation, educational background, socioeconomic indicators, religious or cultural identity where relevant, motivations for engagement, typical concerns, patterns of interaction, and the specific aspects of the subject that resonate with that segment.",
    "Treat audience psychology as a first-class analytical target.",
    "Analyze recurring emotional drivers, cognitive frames, identity formation, trust mechanisms, perceived authority, community norms, and behavioral patterns using evidence from audience behavior across multiple platforms.",
    "The subject's own biography, ideas, publications, and public positions should be included only to the extent necessary to explain the audience and the mechanisms through which influence is created, maintained, or transformed.",
    "Allocate substantially more analytical depth and report space to audience analysis than to descriptive coverage of the subject themselves."
]

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
# ============================================================
# SHARED GUIDELINES
# ============================================================

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

# ============================================================
# AGENT-SPECIFIC GUIDELINES
# ============================================================

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

# ============================================================
# SUMMARY NODE Briefings
# ============================================================

async def summarize_briefings(briefing_1_path: str, briefing_2_path: str, short_query: str) -> str:
    
    with open(briefing_1_path, "r", encoding="utf-8") as f:
        briefing_1 = f.read()
    
    with open(briefing_2_path, "r", encoding="utf-8") as f:
        briefing_2 = f.read()
    
    combined_report = (
        "SOURCE 1:\n" + briefing_1.strip() + "\n\n"
        "SOURCE 2:\n" + briefing_2.strip()
    )
    
    state: GraphState = {
        "subject_intelligence_report": combined_report,
        "user_initial_query": short_query,
    }
    
    print("📝 Compressing the combined briefings with the compressor node...")
    result = compress_subject_intelligence(state)
    
    compressed = result.get("compressed_intelligence", {})
    summary = format_compressed_for_injection(compressed) if compressed else ""
    
    print(f"✅ Compressed summary ready: {len(summary)} chars")
    return summary

# ============================================================
# QUERY BUILDER
# ============================================================

def build_audience_query(subject_name: str, subject_profile: str, combined_summary: str) -> str:
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

async def summarize_single_profile(profile_path: str, short_query: str) -> str:
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_content = f.read()

    if len(profile_content) <= 8000:
        return profile_content

    state: GraphState = {
        "subject_intelligence_report": profile_content,
        "user_initial_query": short_query,
    }

    print("📝 Compressing raw subject profile with the compressor node...")
    result = compress_subject_intelligence(state)

    compressed = result.get("compressed_intelligence", {})
    summary = format_compressed_for_injection(compressed) if compressed else profile_content[:8000]

    print(f"✅ Compressed profile ready: {len(profile_content)} chars -> {len(summary)} chars")
    return summary


# ============================================================
# MAIN
# ============================================================

async def run_audience_intelligence(
    subject_name: str,
    profile_path: str,
    briefing_1_path: str,
    briefing_2_path: str,
    short_query: str,
    max_sections: int = 12,
):
    if not os.path.exists(profile_path):
        print(f"❌ Profile not found: {profile_path}")
        return None

    if not os.path.exists(briefing_1_path):
        print(f"❌ Briefing 1 not found: {briefing_1_path}")
        return None

    if not os.path.exists(briefing_2_path):
        print(f"❌ Briefing 2 not found: {briefing_2_path}")
        return None

    combined_summary = await summarize_briefings(briefing_1_path, briefing_2_path, short_query)
    
    # STEP 2: Read & compress profile
    subject_profile = await summarize_single_profile(profile_path, short_query)

    # STEP 3: Build audience query with profile + combined summary
    full_query = build_audience_query(subject_name, subject_profile, combined_summary)

    # STEP 4: Run Audience Agent  make_research
    state: GraphState = {
        "user_initial_query": short_query,
        "chain_input": {
            "query": full_query,
            "guidelines": audience_guidelines,
            "follow_guidelines": True,
            "max_sections": max_sections,
            "verbose": True,
            "prompt_type": "audience",
            "mcp_configs": mcp_configs,
            "mcp_strategy": "fast",
        },
        "mcp_configs": mcp_configs,
        "mcp_strategy": "fast",
        "prompt_type": "audience",
        "identity_data": {
            "needs_reprocessing": False,
            "feedback_notes": ""
        },
        "research_iteration": 0,
    }

    print("⏳ Running Audience Intelligence Agent...")
    print(f"   📄 Profile: {os.path.basename(profile_path)}")
    print(f"   📄 Combined Summary: {len(combined_summary)} chars")
    print(f"   🔧 prompt_type: {state['prompt_type']}")
    print(f"   🔧 mcp_strategy: {state['mcp_strategy']}")
    print(f"   🔧 mcp_configs: {len(state['mcp_configs'])} server(s)")
    
    # Force the pipeline to use the Audience system prompt for this run
    # (keeps default behavior unchanged elsewhere)
    state["prompt_type"] = "audience"
    state["chain_input"]["prompt_type"] = "audience"

    result = await make_research(state)
    
    identity_result = result.get("identity_data", {})
    report = identity_result.get("report", "")
    sources = identity_result.get("sources", [])
    costs = identity_result.get("costs", 0.0)

    output_path = f"{short_query}_audience_intelligence.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Saved: {output_path}")
    print(f"   Length : {len(report)} chars")
    print(f"   Sources: {len(sources)}")
    print(f"   Costs  : {costs}")

    return identity_result


if __name__ == "__main__":
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    asyncio.run(run_audience_intelligence(
        subject_name="Sheikh Mostafa Al-Adawy",
        profile_path=os.path.join(
            project_root,
            "outputs",
            "run_150f010a03c049fb8ae722c0541ad5d4",
            "f491795c8c444e19af4c212b3b2b767e.md",
        ),
        briefing_1_path=os.path.join(
            project_root,
            "outputs",
            "run_f72fdfbdb74642b59e8a8eb3eb9e8188",
            "b113dfd89d214e61ac82e1958b61dc84.md",
        ),
        briefing_2_path=os.path.join(
            project_root,
            "outputs",
            "run_f72fdfbdb74642b59e8a8eb3eb9e8188",
            "b113dfd89d214e61ac82e1958b61dc84.md",
        ),  # غير المسار
        short_query="MostafaAlAdawy",
        max_sections=4,
    ))