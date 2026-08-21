# subject_intelligence_agent.py

import asyncio
import os
import sys
from Nodes.GPT_ResearcherNode.ResearchNode import make_research
from StateGraph import GraphState

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

# ============================================================
# LAYERS - SUBJECT ONLY
# ============================================================
shared_guidelines = [
    # ============================================================
    # EVIDENCE & ATTRIBUTION
    # ============================================================
    "Collect evidence from multiple independent sources before drawing any conclusion. "
    "A minimum of three independent sources is required before treating any claim as established.",

    "Every factual claim must be traceable to a specific source. "
    "If a source cannot be identified, mark the claim explicitly as [UNVERIFIED] and do not present it as fact.",

    "Direct quotations require a direct URL or document reference to the exact source. "
    "If the original text or recording cannot be located, do not quote — paraphrase with source attribution instead.",

    "Separate the subject's own stated positions from descriptions, labels, or accusations "
    "made by supporters, critics, media outlets, or third parties. "
    "Never present external characterizations as established facts about the subject.",

    "Prefer reconstructing the subject's worldview from their own recurring statements, "
    "writings, speeches, lectures, and documented works — not from how opponents or supporters describe them.",

    # ============================================================
    # IDEOLOGICAL LABELING
    # ============================================================
    "Do not assign ideological labels (e.g. Madkhali, Ikhwani, Jihadi, Liberal) "
    "unless the subject has explicitly self-identified with that label, "
    "or the label is supported by at least three independent and reliable sources "
    "that provide specific behavioral or textual evidence — not mere association or accusation.",

    "Treat ideological classification as a conclusion to be earned by evidence, not a starting assumption. "
    "When evidence is insufficient for a label, describe observable positions and patterns instead.",

    # ============================================================
    # SAMPLING & REPRESENTATIVENESS
    # ============================================================
    "Build a broad and representative map of the subject's recurring ideas, positions, and works "
    "before analyzing individual examples. "
    "Do not allow one or two high-profile or viral incidents to dominate the analysis.",

    "If a particular event or statement appears more than twice across different sections, "
    "this is a signal of over-reliance. Actively seek additional independent examples "
    "to represent the same pattern before continuing.",

    "Distinguish between a subject's foundational recurring positions "
    "and isolated statements made in specific contexts. "
    "Weight recurring patterns significantly higher than single incidents.",

    # ============================================================
    # INFERENCE vs FACT
    # ============================================================
    "Explicitly mark the epistemic status of every major claim using one of: "
    "[VERIFIED], [STRONG EVIDENCE], [REASONABLE INFERENCE], or [INSUFFICIENT EVIDENCE]. "
    "Never present inference as verified fact.",

    "Audience demographics, motivations, and psychological profiles are almost always inferred. "
    "Label them clearly as [INFERRED FROM PATTERNS] and identify what observable evidence the inference is based on.",

    # ============================================================
    # SOURCE QUALITY
    # ============================================================
    "Prioritize primary sources: the subject's own content, books, lectures, interviews, "
    "and documented statements. Secondary sources (news articles, Wikipedia, advocacy organizations) "
    "are supporting evidence only — never the sole basis for a major claim.",

    "If primary sources on a topic cannot be found, explicitly state: "
    "'Primary source not located. The following is based on secondary reporting.' "
    "Do not silently substitute secondary sources for primary ones.",

    "When only secondary sources are available, assess and state their reliability. "
    "Advocacy organizations, political opponents, and state media each carry specific biases "
    "that must be acknowledged when their reporting is used.",

    # ============================================================
    # CONFLICTS & GAPS
    # ============================================================
    "When two or more sources conflict on any fact, present all versions explicitly, "
    "identify each source, and flag the conflict. Never silently resolve a conflict by choosing one version.",

    "Do not omit a section because information is unavailable. "
    "Instead write: 'Insufficient reliable evidence found on this topic.' "
    "Visible gaps are more valuable than silent omissions.",

    # ============================================================
    # OUTPUT DISCIPLINE
    # ============================================================
    "Prioritize structured knowledge extraction over narrative writing. "
    "The output should read as an intelligence document, not a biography or an essay.",

    "Avoid repeating the same information across multiple sections. "
    "Each section must contribute new knowledge. "
    "If a point was already established, reference it — do not restate it.",

    "Produce findings grounded strictly in empirical evidence that support downstream intelligence analysis and knowledge graph construction.",
]

identity_worldview_layer = {
    "name": "Identity & Worldview Layer",
    "objective": "Establish the subject's public identity, "
                 "fundamental worldview, and epistemological framework.",
    "extraction_tasks": [
        "Identify the subject's core biographical foundation, "
        "key milestones, and historical context.",
        "Extract the subject's fundamental worldview, "
        "core beliefs, and hierarchy of values.",
        "Identify the primary knowledge sources and authorities relied upon.",
        "Analyze the epistemological methodology used to evaluate "
        "evidence and justify truth claims.",
        "Extract the primary cognitive models and reasoning patterns "
        "used to explain complex societal issues.",
        "Identify consistent ideological characteristics and positions "
        "on major social, political, or religious issues — "
        "based on the subject's own documented output only.",
        "Explain how different ideas connect into one internally coherent belief system.",
    ],
}

ideas_ideology_layer = {
    "name": "Ideas & Ideology Intelligence",
    "objective": "Reverse engineer the subject's intellectual system, "
                 "core ideas, belief structure, and ideological orientation.",
    "extraction_tasks": [
        "Identify the subject's most influential ideas and recurring intellectual themes "
        "across a broad and representative sample of their work — "
        "not limited to the most viral or controversial examples.",
        "Extract the subject's core beliefs, values, principles, and long-term objectives.",
        "Identify ideological positions supported by evidence across major domains. "
        "For each position, cite at least two independent examples from different time periods.",
        "Distinguish foundational beliefs from secondary opinions "
        "or context-specific positions.",
        "Identify recurring assumptions about human nature, authority, morality, "
        "justice, social order, tradition, and change — "
        "only when supported by multiple independent pieces of evidence.",
        "Explain how different ideas connect into a coherent intellectual framework.",
        "Identify which ideas are central to the subject's public identity "
        "and long-term influence.",
        "Identify ideas that consistently generate support, criticism, "
        "controversy, or polarization.",
    ],
}

epistemology_layer = {
    "name": "Epistemology & Reasoning Intelligence",
    "objective": "Reverse engineer how the subject evaluates knowledge, "
                 "forms judgments, and justifies truth claims.",
    "extraction_tasks": [
        "Identify the primary sources of authority used to support claims and decisions.",
        "Explain how the subject evaluates evidence and determines credibility.",
        "Identify recurring reasoning patterns, analytical frameworks, "
        "and decision-making approaches.",
        "Extract the principles used to distinguish facts, opinions, "
        "beliefs, and uncertainty.",
        "Analyze how the subject responds to conflicting evidence, "
        "criticism, ambiguity, and uncertainty.",
        "Identify recurring logical structures, assumptions, and cognitive models "
        "used to explain complex issues.",
        "Explain how the subject constructs legitimacy, expertise, "
        "and intellectual credibility.",
        "Identify recurring patterns that remain stable across different topics and contexts.",
    ],
}

narrative_communication_layer = {
    "name": "Narrative & Communication Intelligence",
    "objective": "Reverse engineer how the subject communicates ideas, "
                 "frames information, and builds persuasive narratives.",
    "extraction_tasks": [
        "Identify the subject's dominant communication style "
        "and recurring messaging patterns.",
        "Extract recurring narratives, frames, themes, metaphors, "
        "analogies, symbols, and storytelling techniques.",
        "Analyze how complex ideas are simplified, structured, "
        "and adapted for different audiences.",
        "Identify recurring persuasion strategies, emotional appeals, "
        "and audience engagement techniques.",
        "Explain how authority, credibility, and expertise "
        "are established and reinforced.",
        "Identify recurring linguistic patterns, terminology, "
        "catchphrases, and stylistic characteristics.",
        "Analyze how controversial or sensitive topics are framed and communicated.",
        "Identify communication patterns that consistently generate "
        "trust, engagement, influence, or controversy.",
    ],
}

# ============================================================
# AGENT-SPECIFIC GUIDELINES
# ============================================================

subject_guidelines = shared_guidelines + [
    "This run is explicitly scoped to the subject only. "
    "Focus exclusively on the subject's ideas, methodology, worldview, epistemology, "
    "public identity, and communication style.",

    "Do not analyze the audience, community, followers, ecosystem, diffusion dynamics, "
    "or influence pathways in this run. If audience-related material appears, treat it only as background context.",

    "Search for primary sources first: the subject's own books, "
    "lectures, videos, interviews, and documented statements. "
    "Use at least 5 distinct content pieces from the subject's own output "
    "before drawing conclusions about their worldview.",

    "When analyzing ideology or methodology, draw examples from "
    "multiple topic domains and multiple time periods. "
    "Do not use the same example more than once across different sections.",
]

# ============================================================
# QUERY BUILDER
# ============================================================

def build_subject_query(subject_name: str, subject_profile: str) -> str:
    layers = [
        identity_worldview_layer,
        ideas_ideology_layer,
        epistemology_layer,
        narrative_communication_layer,
    ]

    lines = [
        "TASK: Subject Intelligence Profile",
        "",
        f"Subject: {subject_name}",
        "",
        "=== SUBJECT PROFILE CONTEXT ===",
        subject_profile.strip(),
        "===============================",
        "",
        "OBJECTIVE:",
        "Reverse engineer the subject's intellectual system, worldview, epistemology,",
        "and communication methodology.",
        "This run is about the subject only. Audience, followers, and ecosystem dynamics are context only.",
        "This is NOT a biography. Extract structured, reusable knowledge.",
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

# ============================================================
# MAIN
# ============================================================

async def run_subject_intelligence(
    subject_name: str,
    profile_path: str,
    short_query: str,
    max_sections: int = 4,
):
    if not os.path.exists(profile_path):
        print(f"❌ Profile not found: {profile_path}")
        return None

    with open(profile_path, "r", encoding="utf-8") as f:
        subject_profile = f.read()

    full_query = build_subject_query(subject_name, subject_profile)
    mcp_configs = build_audience_mcp_configs()

    # ضبط الـ State بحيث يتوافق مع الـ Schema الخاصة بـ IdentityData
    state: GraphState = {
        "user_initial_query": short_query,
        "chain_input": {
            "query": full_query,
            "guidelines": subject_guidelines,
            "follow_guidelines": True,
            "max_sections": max_sections,
            "verbose": True,
            "prompt_type": "subject",
            "mcp_configs": mcp_configs,
        },
        "prompt_type": "subject",
        "mcp_configs": mcp_configs,
        "identity_data": {
            "needs_reprocessing": False,  # القيمة الافتراضية المطلوبة
            "feedback_notes": ""
        },
        "research_iteration": 0,
    }

    print("[HOURGLASS] Running Subject Intelligence Agent...")
    result = await make_research(state)
    
    # التعامل مع المخرجات المتوافقة مع هيكل الـ identity_data
    identity_result = result.get("identity_data", {})
    report = identity_result.get("report", "")
    sources = identity_result.get("sources", [])
    costs = identity_result.get("costs", 0.0)

    output_path = f"{short_query}_subject_intelligence.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[OK] Saved: {output_path}")
    print(f"   Length : {len(report)} chars")
    print(f"   Sources: {len(sources)}")
    print(f"   Costs  : {costs}")

    return identity_result


if __name__ == "__main__":
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    asyncio.run(run_subject_intelligence(
        subject_name="Sheikh Mostafa Al-Adawy",
        profile_path=os.path.join(
            project_root, "mostafa_el_adawy_the_egyptian_salafai_report.md"
        ),
        short_query="MostafaAlAdawy",
        max_sections=4,
    ))