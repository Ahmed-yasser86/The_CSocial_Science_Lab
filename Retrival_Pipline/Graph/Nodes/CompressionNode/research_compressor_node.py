from typing import Any, Dict, Optional
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from StateGraph import GraphState
from Ingestion_Pipline.config.settings import ChatModelSettings
from Retrival_Pipline.Graph.Chains.ChainUtil import build_chat_model


class CompressedIntelligence(BaseModel):
    """Structured compression of intelligence reports for downstream nodes.
    
    This compression format is designed to:
    1. Preserve key findings from previous nodes
    2. Provide context for subsequent intelligence analysis
    3. Avoid redundant research in downstream nodes
    4. Maintain the flow of information through the graph
    """

    covered_topics: str = Field(
        description="Bullet-point summary of topics already researched and confirmed with evidence. "
                   "This helps downstream nodes avoid repeating the same research."
    )
    confirmed_positions: str = Field(
        description="Key verified positions, beliefs, or patterns extracted from the report. "
                   "This provides established context for downstream analysis."
    )
    available_insights: str = Field(
        description="Concrete evidence and observations from the report about the subject, their audience, "
                   "and their ecosystem. This forms the factual basis for downstream analysis."
    )
    profile_context: str = Field(
        description="Contextual information about the subject's characteristics, priorities, communication style, "
                   "audience relationships, and ecosystem role. This helps downstream nodes understand "
                   "how to approach their specific intelligence tasks."
    )
    intelligence_type: str = Field(
        description="Type of intelligence being compressed (subject, audience, or ecosystem). "
                   "This helps downstream nodes understand the context of the information."
    )


llm = build_chat_model()
llm_with_structured_output = llm.with_structured_output(CompressedIntelligence)


system = """
You are an intelligence compression specialist in a multi-stage intelligence analysis pipeline.

Your role is to compress intelligence reports from one stage to provide context for the next stage.
This enables a sequential flow of information where each node builds on the previous one's findings.

Key principles:
1. Preserve the factual content from the source report
2. Structure the information for easy consumption by downstream nodes
3. Avoid introducing new analysis, speculation, or recommendations
4. Maintain clear separation between established facts and contextual information

For this task, you will receive an intelligence report and must produce a structured compression
that includes the following sections:

1. COVERED TOPICS
   - List each topic already researched and confirmed by the report
   - Use concise bullet points (1-2 lines each)
   - Include only topics with supporting evidence in the report
   - This helps downstream nodes avoid redundant research

2. CONFIRMED POSITIONS
   - Extract only the subject's verified positions, beliefs, or patterns
   - Focus on evidence-backed assertions from the report
   - Use concise bullet points
   - This provides established context for downstream analysis

3. AVAILABLE INSIGHTS
   - Extract concrete evidence about the subject, their audience, and ecosystem
   - Present as factual observations, not analysis or speculation
   - Include both positive findings and limitations of the current report
   - This forms the factual basis for downstream analysis

4. PROFILE CONTEXT
   - Summarize the subject's characteristics, priorities, and communication style
   - Describe their audience relationships and ecosystem role
   - Keep this grounded strictly in the report content
   - This helps downstream nodes understand how to approach their tasks

5. INTELLIGENCE TYPE
   - Specify the type of intelligence (subject, audience, or ecosystem)
   - This helps downstream nodes understand the context

Output Rules:
- Be concise and direct - use bullet points where appropriate
- Do not rewrite the report as prose
- Do not invent evidence, claims, or analysis beyond what's in the report
- Do not provide instructions or recommendations for downstream nodes
- If the report has limitations, state them explicitly in the available insights
- Maintain clear separation between the different sections
- Do not add extra fields or explanatory paragraphs beyond the required structure
"""


compress_prompt = ChatPromptTemplate.from_messages([
    ("system", system),
    ("human", "Intelligence Report to Compress:\n\n{report}\n\nIntelligence Type: {intelligence_type}"),
])


intelligence_compressor = compress_prompt | llm_with_structured_output



def compress_intelligence_report(state: GraphState, report_type: str = "subject") -> Dict[str, Any]:
    """
    Compresses an intelligence report into structured briefing for downstream nodes.
    
    This function extracts key information from a completed intelligence report and
    compresses it into a structured format that can be used by subsequent nodes in the graph.
    
    Args:
        state (GraphState): The current graph state containing reports
        report_type (str): Type of report to compress (subject, audience, or ecosystem)
        
    Returns:
        Dict[str, Any]: Updated state with compressed intelligence
    """
    # Get the appropriate report from state
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
                "intelligence_type": report_type
            }
        }
    
    print(f"⏳ Compressing {report_type.capitalize()} Intelligence Report...")
    print(f"   Report length: {len(report_content)} characters")
    
    # Get context about the subject from state
    user_query = state.get("user_initial_query", "")
    print(f"   Subject: {user_query}")
    
    try:
        result: CompressedIntelligence = intelligence_compressor.invoke({
            "report": report_content,
            "intelligence_type": report_type
        })
        
        compressed = {
            "covered_topics": result.covered_topics,
            "confirmed_positions": result.confirmed_positions,
            "available_insights": result.available_insights,
            "profile_context": result.profile_context,
            "intelligence_type": report_type,
            "source_report": report_type,
            "compression_timestamp": datetime.now().isoformat()
        }
        
        print(f"✅ {report_type.capitalize()} Intelligence compression complete.")
        covered_count = len(result.covered_topics.split("\n"))
        confirmed_count = len(result.confirmed_positions.split("\n"))
        print(f"   Covered topics: {covered_count} items")
        print(f"   Confirmed positions: {confirmed_count} items")
        
        return {
            **state,
            "compressed_intelligence": compressed,
        }
        
    except Exception as e:
        print(f"❌ Error compressing {report_type} intelligence: {str(e)}")
        return {
            **state,
            "compressed_intelligence": {
                "covered_topics": "",
                "confirmed_positions": "",
                "available_insights": f"Compression failed: {str(e)}",
                "profile_context": "",
                "intelligence_type": report_type
            }
        }



def compress_subject_intelligence(state: GraphState) -> Dict[str, Any]:
    """
    Convenience wrapper used by the Intelligence nodes and the research
    compressor tests.

    It expects the raw subject report to live under ``subject_intelligence_report``
    (as produced by the summarization / briefing nodes) and compresses it as a
    "subject" report, returning the same ``{"compressed_intelligence": ...}``
    shape as :func:`compress_intelligence_report`.
    """
    report_content = state.get("subject_intelligence_report", "")
    sub_state: GraphState = {
        **state,
        "reports": {"subject": {"content": report_content}},
    }
    return compress_intelligence_report(sub_state, "subject")


def format_compressed_for_injection(compressed: dict) -> str:
    """
    Formats the compressed intelligence dict into a clean string
    ready to be injected into downstream nodes' queries.
    
    This formatted string provides context about what has already been researched
    and established, helping downstream nodes build on previous findings.
    """
    intelligence_type = compressed.get("intelligence_type", "unknown").upper()
    
    return "\n".join([
        f"=== {intelligence_type} INTELLIGENCE BRIEFING ===",
        f"(Compressed from {compressed.get('source_report', 'unknown')} report)",
        "",
        "PREVIOUSLY COVERED TOPICS (do not repeat):",
        compressed.get("covered_topics", "No topics covered."),
        "",
        "ESTABLISHED CONTEXT (use as factual basis):",
        compressed.get("confirmed_positions", "No confirmed positions."),
        "",
        "AVAILABLE INSIGHTS:",
        compressed.get("available_insights", "No insights available."),
        "",
        "PROFILE CONTEXT:",
        compressed.get("profile_context", "No profile context available."),
        "",
        f"Compressed: {compressed.get('compression_timestamp', 'unknown time')}",
        f"=====================================",
    ])