# Chains/IdentityResearch.py
from typing import TypedDict, List
from gpt_researcher import GPTResearcher


class IdentityResult(TypedDict):
    report: str
    source_urls: list[str]
    research_sources: list[dict]
    costs: float
    subtopics: list[str]


IDENTITY_PROMPT = """\
Your goal is to establish the verified identity of the subject named in the \
query. The final output report must strictly reflect that the person we are looking for carries this exact profile structure and schema:

# Profile Schema:
- Subject Name / Full Legal Name: [Full name and any known aliases, kunyas, or nicknames]
- Biographical Anchors: [Date and place of birth, nationality, current location/residence if known]
- Digital Presence & Websites: [Official website, personal blogs, portfolio links, and any web pages or online properties directly belonging to the subject]
- Verified Social Media Handles: [Platform names and exact links/handles]
- Disambiguation Details: [Any distinguishing details that prevent confusion with someone else sharing a similar name]

Focus specifically on these identity anchors and do not include deep biography, career opinions, or controversies.

Rules:
- Every fact must be tied to its source inline.
- If two sources conflict on any identity detail, state both and flag the conflict explicitly.
- If a detail is confirmed by only one source, mark it "single-source, unverified".
- Make sure to explicitly gather and list all electronic websites and web links associated with the subject under the "Digital Presence & Websites" section.
"""


async def research_identity(query: str) -> IdentityResult:
    researcher = GPTResearcher(
        query=query,
        report_type="research_report",
        verbose=True,
    )
    await researcher.conduct_research()
    report = await researcher.write_report(custom_prompt=IDENTITY_PROMPT)

    return IdentityResult(
        report=report,
        source_urls=researcher.get_source_urls(),
        research_sources=researcher.get_research_sources(),
        costs=researcher.get_costs(),
        subtopics=await researcher.get_subtopics(),
    )