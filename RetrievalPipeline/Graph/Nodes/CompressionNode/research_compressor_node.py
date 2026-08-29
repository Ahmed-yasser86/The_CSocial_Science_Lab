from typing import Any, Dict, Optional
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from StateGraph import GraphState
from Ingestion_Pipline.config.settings import ChatModelSettings
from RetrievalPipeline.Graph.Chains.ChainUtil import build_chat_model


class CompressedIntelligence(BaseModel):
    """Structured compression of intelligence reports for downstream nodes.

    Designed to:
    1. Preserve key findings (with epistemic status + sources) from previous nodes
    2. Provide focused context for a specific downstream consumer
    3. State explicit GAPS the next node should investigate (no redundant research)
    4. Maintain the flow of information through the graph
    """

    covered_topics: str = Field(
        description="Bullet-point summary of topics already researched and confirmed with evidence. "
                    "This helps the downstream node avoid repeating the same research."
    )
    confirmed_positions: str = Field(
        description="Key verified positions, beliefs, or patterns extracted from the report, "
                    "each tagged with its epistemic status ([VERIFIED]/[STRONG EVIDENCE]/"
                    "[REASONABLE INFERENCE]/[INFERRED FROM PATTERNS])."
    )
    available_insights: str = Field(
        description="Concrete evidence and observations from the report about the subject, their audience, "
                    "and their ecosystem. Factual basis for downstream analysis."
    )
    profile_context: str = Field(
        description="Contextual information about the subject's characteristics, priorities, communication "
                    "style, audience relationships, and ecosystem role."
    )
    key_claims_with_sources: str = Field(
        description="The most decision-relevant claims, one per line, each formatted as: "
                    "'- [STATUS] <claim> -- <source url or document>'. Preserve the [VERIFIED]/"
                    "[INFERRED FROM PATTERNS] markers exactly as they appear in the source report."
    )
    open_questions: str = Field(
        description="Only when a target node is specified. Concrete gaps the TARGET node should "
                    "investigate next, phrased as questions. Must NOT repeat covered_topics."
    )
    intelligence_type: str = Field(
        description="Type of intelligence being compressed (subject, audience, or ecosystem)."
    )
    target_node: Optional[str] = Field(
        default=None,
        description="Downstream consumer this briefing is built for (audience/ecosystem), if any.",
    )


llm = build_chat_model()
llm_with_structured_output = llm.with_structured_output(CompressedIntelligence)


BASE_SYSTEM = """
You are an intelligence compression specialist in a multi-stage intelligence analysis pipeline.

Your role is to compress an intelligence report from one stage so it can provide focused,
reusable context for the next stage. Each downstream node builds on the previous one's findings.

Key principles:
1. Preserve factual content and epistemic status from the source report.
2. Structure information for easy consumption by the downstream node.
3. Keep clear separation between established facts and contextual information.
4. Preserve provenance: every key claim must keep its source reference and its epistemic
   marker ([VERIFIED], [STRONG EVIDENCE], [REASONABLE INFERENCE], [INFERRED FROM PATTERNS],
   [INSUFFICIENT EVIDENCE]). Do not strip or weaken these markers.

Produce a structured compression with these sections:

1. COVERED TOPICS
   - Topics already researched and confirmed by the report (concise bullets).
   - Only topics with supporting evidence. Helps the downstream node avoid redundant research.

2. CONFIRMED POSITIONS
   - The subject's verified positions/beliefs/patterns, each tagged with its epistemic status.
   - Evidence-backed assertions only. Concise bullets.

3. AVAILABLE INSIGHTS
   - Concrete evidence about the subject, audience, and ecosystem as factual observations.
   - Include both positive findings and limitations of the current report.

4. PROFILE CONTEXT
   - Subject characteristics, priorities, communication style, audience relationships, ecosystem role.
   - Grounded strictly in the report.

5. KEY CLAIMS WITH SOURCES
   - The most decision-relevant claims, one per line: '- [STATUS] <claim> -- <source url or document>'.
   - These are the reusable evidence units for the downstream node.

6. INTELLIGENCE TYPE
   - subject / audience / ecosystem.

Output Rules:
- Be concise and direct; use bullets where appropriate.
- Do not rewrite the report as prose.
- Do not invent evidence, claims, or analysis beyond what's in the report.
- Do not add extra fields or explanatory paragraphs beyond the required structure.
"""

TARGET_INSTRUCTIONS = {
    "audience": (
        "TARGET NODE = AUDIENCE INTELLIGENCE. Emphasize communication style, audience relationships, "
        "and community dynamics in PROFILE CONTEXT and CONFIRMED POSITIONS. In the OPEN QUESTIONS "
        "section, list the specific gaps the audience node must investigate (segments, motivations, "
        "community structures, influential followers). Do NOT repeat covered topics."
    ),
    "ecosystem": (
        "TARGET NODE = ECOSYSTEM INTELLIGENCE. Emphasize institutional, systemic, and macro-environmental "
        "context in PROFILE CONTEXT and AVAILABLE INSIGHTS. In the OPEN QUESTIONS section, list the specific "
        "gaps the ecosystem node must investigate (institutions, state-society relations, systemic risks, "
        "cross-entity dynamics). Do NOT repeat covered topics."
    ),
}


def _build_prompt(target_node: Optional[str]):
    system = BASE_SYSTEM
    if target_node in TARGET_INSTRUCTIONS:
        system += "\n\n" + TARGET_INSTRUCTIONS[target_node]
    return ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "Intelligence Report to Compress:\n\n{report}\n\nIntelligence Type: {intelligence_type}"),
    ])


# Legacy alias used by older tests/examples (generic, no target node).
intelligence_compressor = _build_prompt(None) | llm_with_structured_output


def _compressor_for(target_node: Optional[str]):
    if target_node is None:
        return intelligence_compressor
    return _build_prompt(target_node) | llm_with_structured_output


def compress_intelligence_report(
    state: GraphState,
    report_type: str = "subject",
    target_node: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compresses an intelligence report into a structured briefing for downstream nodes.

    Args:
        state: Graph state containing reports.
        report_type: Type of report to compress (subject, audience, ecosystem).
        target_node: Optional consumer this briefing is built for ("audience"/"ecosystem").
            When set, the compression is scoped to that node's needs and includes an
            OPEN QUESTIONS (gaps) section.

    Returns:
        State with ``compressed_intelligence`` populated.
    """
    reports = state.get("reports", {})
    report_data = reports.get(report_type, {})
    report_content = report_data.get("content", "")

    if not report_content:
        print(f"⚠️  No {report_type} intelligence report found in state. Skipping compression.")
        return {
            **state,
            "compressed_intelligence": {
                "covered_topics": "",
                "confirmed_positions": "",
                "available_insights": f"No {report_type} report provided.",
                "profile_context": "No profile context available.",
                "key_claims_with_sources": "",
                "open_questions": "",
                "intelligence_type": report_type,
                "target_node": target_node,
            },
        }

    print(f"⏳ Compressing {report_type.capitalize()} Intelligence Report (target={target_node or 'generic'})...")
    print(f"   Report length: {len(report_content)} characters")

    try:
        result: CompressedIntelligence = _compressor_for(target_node).invoke({
            "report": report_content,
            "intelligence_type": report_type,
        })

        compressed = {
            "covered_topics": getattr(result, "covered_topics", ""),
            "confirmed_positions": getattr(result, "confirmed_positions", ""),
            "available_insights": getattr(result, "available_insights", ""),
            "profile_context": getattr(result, "profile_context", ""),
            "key_claims_with_sources": getattr(result, "key_claims_with_sources", ""),
            "open_questions": getattr(result, "open_questions", "") or "",
            "intelligence_type": report_type,
            "target_node": target_node,
            "source_report": report_type,
            "compression_timestamp": datetime.now().isoformat(),
        }

        print(f"✅ {report_type.capitalize()} Intelligence compression complete.")
        print(f"   Covered topics: {len([x for x in compressed['covered_topics'].split(chr(10)) if x.strip()])} items")
        print(f"   Key claims w/ sources: {len([x for x in compressed['key_claims_with_sources'].split(chr(10)) if x.strip()])} items")

        # Cache so downstream nodes / resumed runs do not recompute.
        cached = dict(state.get("compressed_reports", {}))
        cached[f"{report_type}->{target_node}"] = compressed
        return {**state, "compressed_intelligence": compressed, "compressed_reports": cached}

    except Exception as e:
        print(f"❌ Error compressing {report_type} intelligence: {str(e)}")
        return {
            **state,
            "compressed_intelligence": {
                "covered_topics": "",
                "confirmed_positions": "",
                "available_insights": f"Compression failed: {str(e)}",
                "profile_context": "",
                "key_claims_with_sources": "",
                "open_questions": "",
                "intelligence_type": report_type,
                "target_node": target_node,
            },
        }


def compress_subject_intelligence(state: GraphState) -> Dict[str, Any]:
    """Convenience wrapper: compress a raw subject report as a 'subject' report."""
    report_content = state.get("subject_intelligence_report", "")
    sub_state: GraphState = {**state, "reports": {"subject": {"content": report_content}}}
    return compress_intelligence_report(sub_state, "subject")


def get_or_compress(
    state: GraphState,
    report_type: str,
    target_node: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a cached compression if present, otherwise compute and cache it."""
    cache = state.get("compressed_reports", {})
    key = f"{report_type}->{target_node}"
    if key in cache:
        return {**state, "compressed_intelligence": cache[key]}
    return compress_intelligence_report(state, report_type, target_node)


# ---------------------------------------------------------------------------
# Reference-document compression (profiles, briefings) — light, no audience/ecosystem framing.
# ---------------------------------------------------------------------------
_REF_SYSTEM = """You are a compression specialist. Summarize the provided reference document into a
concise briefing that preserves key facts, names, dates, figures, and source references.
Keep any epistemic markers ([VERIFIED], [INFERRED FROM PATTERNS], etc.) and cite sources where
present. Do not add analysis, commentary, or recommendations. If the document is already short,
a light trim is enough."""

_ref_prompt = ChatPromptTemplate.from_messages([
    ("system", _REF_SYSTEM),
    ("human", "Reference Document:\n\n{report}"),
])
_ref_chain = _ref_prompt | llm


def compress_reference_doc(content: str) -> str:
    """Compress a raw reference document (profile/briefing) for context injection.

    Unlike compress_subject_intelligence, this does NOT impose the subject-intelligence
    structure, so it is appropriate for profiles and briefings. Short documents are returned
    unchanged.
    """
    if not content:
        return ""
    if len(content) <= 8000:
        return content
    try:
        out = _ref_chain.invoke({"report": content})
        text = getattr(out, "content", None) or str(out)
        return text if text else content[:8000]
    except Exception as e:
        print(f"❌ Reference compression failed: {str(e)}")
        return content[:8000]


def format_compressed_for_injection(compressed: dict, target_node: Optional[str] = None) -> str:
    """
    Format the compressed intelligence dict into a string for downstream injection.

    When ``target_node`` is provided, only the sections relevant to that consumer are
    included, which keeps the (expensive) downstream research prompt focused.
    """
    if compressed is None:
        return ""

    intelligence_type = compressed.get("intelligence_type", "unknown").upper()
    sections = [
        f"=== {intelligence_type} INTELLIGENCE BRIEFING ===",
        f"(Compressed from {compressed.get('source_report', 'unknown')} report)",
        "",
        "PREVIOUSLY COVERED TOPICS (do not repeat):",
        compressed.get("covered_topics", "No topics covered."),
        "",
        "KEY CLAIMS WITH SOURCES (reuse as evidence):",
        compressed.get("key_claims_with_sources", "No claims recorded."),
    ]

    if target_node == "audience":
        sections += [
            "",
            "CONFIRMED POSITIONS (relevant to audience analysis):",
            compressed.get("confirmed_positions", "No confirmed positions."),
            "",
            "PROFILE CONTEXT (communication style & audience relationships):",
            compressed.get("profile_context", "No profile context available."),
        ]
    elif target_node == "ecosystem":
        sections += [
            "",
            "AVAILABLE INSIGHTS (institutional / systemic context):",
            compressed.get("available_insights", "No insights available."),
            "",
            "PROFILE CONTEXT (institutional role & ecosystem position):",
            compressed.get("profile_context", "No profile context available."),
        ]
    else:
        sections += [
            "",
            "ESTABLISHED CONTEXT (use as factual basis):",
            compressed.get("confirmed_positions", "No confirmed positions."),
            "",
            "AVAILABLE INSIGHTS:",
            compressed.get("available_insights", "No insights available."),
            "",
            "PROFILE CONTEXT:",
            compressed.get("profile_context", "No profile context available."),
        ]

    if compressed.get("open_questions"):
        sections += [
            "",
            "OPEN QUESTIONS THE NEXT NODE SHOULD INVESTIGATE (gaps, not repeats):",
            compressed["open_questions"],
        ]

    sections += [
        "",
        f"Compressed: {compressed.get('compression_timestamp', 'unknown time')}",
        f"=====================================",
    ]
    return "\n".join(sections)
