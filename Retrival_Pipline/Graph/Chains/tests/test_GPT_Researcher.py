# # # # import queue_patch              # 1. يمنع 429 من الأساس
# # # import call_model_loud_patch    # 3. يفضح الـ None بدل ما يخفيها
# # # import ReviserAgentPatch        # 4. شبكة أمان أخيرة
# # # import asyncio
# # # from dotenv import load_dotenv

# # # from Nodes.GPT_ResearcherNode.ResearchNode import make_research
# # # from StateGraph import GraphState

# # # load_dotenv()


# # # # ============================================================
# # # # EXTERNAL CONFIGURATIONS & LAYERS (Global Scope)
# # # # ============================================================

# # # epistemic_layer = {
# # #     "name": "Epistemic Layer",
# # #     "objective": """
# # # Reverse engineer how the subject constructs knowledge, evaluates evidence,
# # # forms judgments, resolves disagreement, and establishes epistemic authority.
# # # The goal is to model the subject's reasoning architecture rather than merely
# # # listing beliefs or opinions.
# # # """,
# # #     "research_questions": [
# # #         "What primary knowledge sources does the subject rely on?",
# # #         "Which authorities, texts, institutions, traditions, or individuals are cited most frequently?",
# # #         "Which sources are considered authoritative and which are rejected?",
# # #         "How does the subject construct arguments?",
# # #         "What forms of reasoning appear most frequently (textual, empirical, historical, logical, analogical, moral, theological, scientific, etc.)?",
# # #         "How does the subject evaluate evidence?",
# # #         "What standards are used to distinguish valid from invalid evidence?",
# # #         "How are conflicting pieces of evidence reconciled?",
# # #         "How does the subject interpret ambiguous texts, events, or concepts?",
# # #         "Which interpretive principles appear consistently across different topics?",
# # #         "How does the subject deal with uncertainty, disagreement, or incomplete evidence?",
# # #         "Under what conditions does the subject suspend judgment, express certainty, or revise previous positions?",
# # #         "How does the subject establish intellectual legitimacy and authority?",
# # #         "Why do followers consider the subject knowledgeable or trustworthy?",
# # #         "Identify the underlying epistemological methodology that consistently shapes the subject's work.",
# # #         "Identify recurring assumptions that appear to guide the subject's reasoning.",
# # #         "Reverse engineer the subject's reasoning process from inputs to conclusions.",
# # #         "Identify recurring decision rules, heuristics, and reasoning patterns.",
# # #         "Construct an evidence-based model describing how the subject thinks rather than simply what the subject believes."
# # #     ]
# # # }

# # # identity_layer = {
# # #     "name": "Identity Layer",
# # #     "objective": """
# # # Establish the minimum factual foundation required to understand the subject.
# # # This layer should identify who the subject is, the environments in which they operate,
# # # their historical context, and the major events that shaped their public identity.
# # # Avoid unnecessary biographical detail. Every extracted fact should support
# # # understanding of later analytical layers.
# # # """,
# # #     "research_questions": [
# # #         "Who is the subject?",
# # #         "What roles, professions, positions, or public identities does the subject occupy?",
# # #         "Identify only the biographical information necessary to understand the subject's later influence.",
# # #         "Identify major life events that significantly shaped the subject's development or public role.",
# # #         "Place the subject within the appropriate historical, cultural, political, religious, scientific, professional, or social context.",
# # #         "Construct a timeline of major milestones relevant to understanding the subject's evolution.",
# # #         "Identify organizations, institutions, movements, companies, parties, schools of thought, or communities with which the subject has been significantly associated.",
# # #         "Identify major publications, books, speeches, interviews, projects, media appearances, lectures, or other influential public outputs.",
# # #         "Identify awards, appointments, positions, institutional recognition, or other indicators of public standing whenever applicable.",
# # #         "Explain how the subject is commonly described by supporters, critics, institutions, media, and the wider public whenever sufficient evidence exists.",
# # #         "Produce a concise factual profile that serves as the foundation for all subsequent analytical layers rather than a traditional biography."
# # #     ]
# # # }

# # # analysis_layers = {
# # #     "cognitive_layer": [
# # #         "Reverse-engineer the subject's cognitive architecture rather than merely describing opinions.",
# # #         "Identify the fundamental worldview that consistently organizes the subject's interpretation of reality.",
# # #         "Identify recurring assumptions about human nature, society, morality, authority, knowledge, religion, politics, history, and social order.",
# # #         "Identify the subject's hierarchy of values and determine which values consistently override others when priorities conflict.",
# # #         "Identify the mental models repeatedly used to explain complex events, conflicts, institutions, or social change.",
# # #         "Identify recurring reasoning patterns, heuristics, analogies, causal explanations, and decision frameworks.",
# # #         "Determine whether the subject primarily reasons through scripture, empirical evidence, historical precedent, authority, tradition, logical deduction, personal experience, or combinations of these.",
# # #         "Identify recurring cognitive shortcuts, framing mechanisms, simplifications, or dichotomies whenever supported by evidence.",
# # #         "Explain how different ideas connect into one internally coherent belief system rather than treating each position independently.",
# # #         "Extract a reusable cognitive model capable of explaining future positions based on previously observed reasoning patterns."
# # #     ],
# # #     "epistemic_layer": [
# # #         "Reverse-engineer how the subject decides what should be accepted as true, reliable, legitimate, or authoritative.",
# # #         "Identify the subject's primary sources of knowledge and explain how they are prioritized.",
# # #         "Determine how conflicting evidence is evaluated and resolved whenever sufficient evidence exists.",
# # #         "Identify which authorities, institutions, scholars, traditions, experts, or knowledge systems are repeatedly trusted or rejected.",
# # #         "Analyze recurring standards of evidence, proof, certainty, authenticity, and credibility.",
# # #         "Identify how the subject justifies truth claims and establishes epistemic authority.",
# # #         "Determine whether knowledge is presented as absolute, probabilistic, contextual, evolving, revealed, empirical, or otherwise.",
# # #         "Identify recurring epistemological assumptions that shape the subject's arguments, interpretations, and conclusions.",
# # #         "Explain how the subject's epistemology influences communication style, audience trust, ideological positions, and public influence.",
# # #         "Extract a reusable epistemic model capable of predicting how the subject is likely to evaluate future information."
# # #     ]
# # # }

# # # audience_layer = [
# # #     "Identify every major audience segment surrounding the subject.",
# # #     "Characterize each segment by demographics, geography, education, profession, language, religiosity, political orientation, socioeconomic background, and online behavior whenever evidence allows.",
# # #     "Identify the values, identities, aspirations, fears, grievances, motivations, and psychological needs shared within each audience segment.",
# # #     "Explain why each audience segment is attracted to the subject instead of competing figures.",
# # #     "Explain why different audience segments interpret the same messages differently.",
# # #     "Identify which beliefs resonate most strongly with each audience segment.",
# # #     "Identify which ideological positions attract, repel, or polarize different communities.",
# # #     "Analyze the cultural norms, worldview, moral priorities, identity markers, and shared assumptions that characterize the audience ecosystem.",
# # #     "Identify recurring language, terminology, symbols, narratives, slogans, references, memes, or recurring expressions shared by followers whenever evidence exists.",
# # #     "Identify formal organizations, informal communities, online groups, educational circles, fan communities, discussion spaces, and influential intermediaries.",
# # #     "Identify secondary influencers, moderators, teachers, organizations, or community leaders who amplify or reinterpret the subject's ideas.",
# # #     "Explain how newcomers typically enter the ecosystem.",
# # #     "Explain how trust develops inside the community.",
# # #     "Explain how long-term members differ from casual followers.",
# # #     "Explain how disagreement is handled within the community.",
# # #     "Identify mechanisms that strengthen group cohesion or create internal divisions.",
# # #     "Extract stable behavioral patterns shared across the audience.",
# # #     "Extract recurring motivations, emotional triggers, decision-making heuristics, communication preferences, and information consumption habits.",
# # #     "Extract reusable behavioral rules that could later support Digital Twin simulation rather than merely describing the audience."
# # # ]

# # # network_diffusion_layer = [
# # #     "Map how ideas move from the subject into the wider ecosystem.",
# # #     "Identify the complete diffusion chain from the original message to wider public adoption.",
# # #     "Identify important intermediaries that accelerate, reinterpret, filter, or amplify ideas.",
# # #     "Identify major entities within the ecosystem, including people, organizations, institutions, communities, media outlets, platforms, educational networks, publishers, and recurring collaborators.",
# # #     "Explain the relationships between these entities and estimate their relative importance whenever evidence allows.",
# # #     "Explain how information flows between the subject, followers, secondary influencers, communities, institutions, traditional media, and social media.",
# # #     "Identify feedback loops between the subject and the audience.",
# # #     "Explain whether audience reactions appear to influence the subject's later communication or priorities.",
# # #     "Identify the mechanisms responsible for successful dissemination of ideas.",
# # #     "Explain why certain ideas spread rapidly while others remain limited.",
# # #     "Identify factors that increase or reduce diffusion, credibility, retention, and long-term influence.",
# # #     "Analyze how communities reinforce shared beliefs through discussion, repetition, education, social identity, community norms, algorithmic exposure, or user-generated content.",
# # #     "Identify self-reinforcing feedback loops that sustain influence over time.",
# # #     "Identify ideas, narratives, campaigns, or messages that failed to spread or generated weak engagement whenever evidence exists.",
# # #     "Explain why these ideas failed relative to more successful ones.",
# # #     "Construct a reusable network model describing how influence propagates through the ecosystem rather than simply listing communication channels."
# # # ]

# # # influence_layer = [
# # #     "Identify observable evidence of the subject's influence on individuals, communities, institutions, education, religion, politics, culture, media, public discourse, or professional practice.",
# # #     "Distinguish measurable influence from perceived popularity.",
# # #     "Explain what actually changed as a result of the subject's ideas whenever evidence exists.",
# # #     "Identify which ideas became influential beyond the subject's immediate audience.",
# # #     "Identify which concepts, arguments, terminology, interpretations, or frameworks have been adopted, repeated, cited, or debated by others.",
# # #     "Estimate the relative importance of each major idea within the broader ecosystem.",
# # #     "Analyze how the subject influences identity formation, moral norms, social behavior, decision making, community cohesion, and collective action.",
# # #     "Explain which audience segments appear most influenced and provide the supporting evidence.",
# # #     "Identify relationships with institutions, organizations, educational systems, religious bodies, political actors, media organizations, publishers, or other influential entities whenever evidence exists.",
# # #     "Explain whether influence flows primarily through institutions, communities, media, or interpersonal networks.",
# # #     "Identify ideas, positions, or events that generated unusually high support, criticism, polarization, or public debate.",
# # #     "Explain why these issues became polarizing and which communities were involved.",
# # #     "Assess which elements of the subject's influence appear durable versus temporary.",
# # #     "Identify factors that strengthen, sustain, weaken, or limit long-term influence.",
# # #     "Compare the subject's influence with major comparable figures whenever this improves understanding.",
# # #     "Explain both similarities and distinctive characteristics using documented evidence.",
# # #     "Construct an evidence-based influence model linking ideas, communication, audience, institutions, networks, and observable outcomes rather than describing them independently."
# # # ]

# # # simulation_layer = [
# # #     "Extract the stable belief system that characterizes the typical follower.",
# # #     "Identify the core assumptions, values, priorities, identity markers, and worldview most consistently shared across the ecosystem.",
# # #     "Separate highly stable beliefs from context-dependent opinions.",
# # #     "Extract recurring decision-making heuristics used by followers.",
# # #     "Explain how followers typically evaluate new information, competing opinions, criticism, uncertainty, and authority.",
# # #     "Identify the conditions under which followers are likely to accept, reject, reinterpret, or ignore new ideas.",
# # #     "Extract reusable IF-THEN behavioral rules supported by evidence.",
# # #     "Describe how followers typically react to agreement, disagreement, controversy, criticism, praise, institutional support, or external attacks.",
# # #     "Identify recurring behavioral patterns rather than isolated examples.",
# # #     "Extract the communication style most commonly adopted by followers.",
# # #     "Identify recurring vocabulary, framing strategies, rhetorical techniques, emotional appeals, humor, symbolism, quotations, and conversational norms.",
# # #     "Explain how followers communicate with supporters, critics, and neutral audiences.",
# # #     "Model how followers influence one another.",
# # #     "Identify mechanisms of trust formation, reputation building, social reinforcement, conformity, leadership emergence, and conflict resolution.",
# # #     "Explain how communities maintain cohesion over time.",
# # #     "Extract reusable rules describing how ideas propagate through the ecosystem.",
# # #     "Identify which types of messages are most likely to be shared, defended, debated, ignored, or rejected.",
# # #     "Explain how audience members become secondary distributors of ideas.",
# # #     "Identify how the ecosystem adapts to major criticism, social change, political events, technological shifts, or competing narratives.",
# # #     "Explain which beliefs appear highly resilient and which appear more adaptable.",
# # #     "Clearly distinguish behaviors supported by strong evidence from reasonable analytical inferences.",
# # #     "Explicitly identify uncertainty whenever simulation rules cannot be reliably inferred from available evidence.",
# # #     "Produce the final results as a structured behavioral model suitable for AI simulation rather than a descriptive narrative.",
# # #     "Prioritize reusable behavioral patterns, causal mechanisms, and interaction rules over chronological reporting."
# # # ]

# # # research_questions = [
# # #     "What worldview, ideology, philosophy, epistemology, methodology, or system of thought consistently shapes the subject?",
# # #     "What beliefs, assumptions, values, priorities, and recurring principles define the subject's work?",
# # #     "Which ideas most strongly define the subject's public identity?",
# # #     "Which themes dominate the subject's discourse?",
# # #     "Which intellectual, religious, political, scientific, philosophical, or cultural traditions most strongly influence the subject?",
# # #     "How does the subject define authority, truth, evidence, morality, justice, religion, politics, society, identity, and social order?",
# # #     "How has the subject's worldview, priorities, and rhetoric evolved over time?",
# # #     "Which ideological characteristics consistently appear throughout the subject's discourse?",
# # #     "Does credible evidence indicate recurring patterns such as conservatism, liberalism, progressivism, nationalism, traditionalism, reformism, populism, sectarianism, exclusivism, political mobilization, extremism, discrimination, conspiracy narratives, or similar ideological tendencies?",
# # #     "Which ideological positions receive the strongest emphasis?",
# # #     "Which positions appear central versus peripheral within the subject's overall worldview?",
# # #     "Which controversial ideas most strongly define the subject's public image?",
# # #     "What positions does the subject consistently express regarding women, gender roles, family, children, education, minorities, religious diversity, democracy, secularism, nationalism, political participation, violence, extremism, human rights, freedom of expression, morality, and social norms whenever applicable?",
# # #     "Which positions generate the strongest public support, criticism, or polarization?",
# # #     "How consistent are these positions across different periods and communication channels?",
# # #     "How does the subject communicate complex ideas to different audiences?",
# # #     "Which rhetorical strategies, persuasion techniques, framing methods, emotional appeals, narratives, symbolism, historical references, educational approaches, and authority-building mechanisms repeatedly appear?",
# # #     "How does the communication style reinforce the subject's ideology and influence?",
# # #     "Who are the primary audience segments surrounding the subject?",
# # #     "Which demographic, geographic, ideological, religious, educational, linguistic, professional, cultural, socioeconomic, and age groups appear most engaged?",
# # #     "How do different audience segments differ in motivations, values, expectations, identities, and behaviors?",
# # #     "Why do different audiences discover, trust, follow, defend, criticize, or remain engaged with the subject?",
# # #     "Which psychological needs, aspirations, frustrations, fears, identities, or goals appear to be satisfied by the subject's content?",
# # #     "What ideological tendencies characterize the audience itself?",
# # #     "What shared cultural assumptions, values, moral frameworks, identities, and beliefs appear repeatedly within the audience?",
# # #     "Which audience segments interpret the subject differently?",
# # #     "Which communities selectively adopt certain ideas while rejecting others?",
# # #     "How homogeneous or diverse is the audience ecosystem?",
# # #     "How is the audience socially organized?",
# # #     "Identify communities, organizations, online groups, discussion spaces, fan networks, educational circles, and informal social structures surrounding the subject.",
# # #     "Identify influential followers, moderators, secondary influencers, organizations, or institutions that amplify the subject's influence.",
# # #     "How do ideas spread inside the audience ecosystem?",
# # #     "Which ideas resonate most strongly with which audience segments?",
# # #     "Which ideas generate the strongest approval?",
# # #     "Which ideas generate disagreement, criticism, or polarization?",
# # #     "Which ideas spread organically and which fail to spread?",
# # #     "How do different audience communities react differently to the same ideas?",
# # #     "Explain the relationship between the subject's ideas, audience composition, communication style, and observed influence rather than analyzing them independently.",
# # #     "What types of content does the subject produce?",
# # #     "Which content formats generate the highest engagement?",
# # #     "What recurring narratives, topics, framing patterns, communication structures, and storytelling techniques repeatedly appear?",
# # #     "How are messages adapted across different media platforms?",
# # #     "Why does the audience perceive the subject as credible or authoritative?",
# # #     "Which signals create legitimacy and trust?",
# # #     "How does the subject establish expertise, authenticity, or religious, political, scientific, or cultural authority?",
# # #     "How is long-term credibility maintained?",
# # #     "Through which mechanisms do the subject's ideas influence individuals, communities, institutions, and public discourse?",
# # #     "Which ideas spread most successfully?",
# # #     "Which ideas become embedded within community identity?",
# # #     "Which ideas influence observable real-world behavior?",
# # #     "How does influence propagate from the subject to followers and then through wider social networks?",
# # #     "What measurable or observable impacts exist?",
# # #     "Analyze the subject's ecosystem across YouTube, Facebook, Instagram, TikTok, X/Twitter, websites, podcasts, newsletters, television, books, and other communication channels.",
# # #     "Which platforms are most important for growth, authority, engagement, and long-term influence?",
# # #     "What platform-specific audience behaviors appear?",
# # #     "Analyze audience language, comments, discussions, debates, and reactions whenever evidence is available.",
# # #     "Who are the subject's principal supporters, critics, ideological rivals, competing influencers, organizations, and alternative schools of thought?",
# # #     "Why do disagreements exist?",
# # #     "How do different audience groups respond to criticism and controversy?",
# # #     "Which controversies produce lasting polarization?",
# # #     "How have the subject's ideas, communication, audience, reputation, and influence evolved over time?",
# # #     "Which historical, technological, political, institutional, cultural, or social events explain these changes?",
# # #     "Identify the major turning points in the subject's influence trajectory.",
# # #     "Extract stable ideological patterns.",
# # #     "Extract stable moral frameworks.",
# # #     "Extract recurring cognitive biases.",
# # #     "Extract recurring argument structures.",
# # #     "Extract recurring persuasion mechanisms.",
# # #     "Extract identity markers.",
# # #     "Extract cultural assumptions.",
# # #     "Extract emotional triggers.",
# # #     "Extract trust formation mechanisms.",
# # #     "Extract authority recognition patterns.",
# # #     "Extract decision-making heuristics.",
# # #     "Extract information consumption habits.",
# # #     "Extract behavioral rules.",
# # #     "Extract disagreement and polarization mechanisms.",
# # #     "Extract conditions that increase or decrease influence.",
# # #     "Extract reusable behavioral rules suitable for agent simulation.",
# # #     "Construct a reusable Digital Twin of both the subject and the surrounding audience ecosystem rather than a descriptive report.",
# # #     "Focus on extracting reusable cognitive, ideological, cultural, behavioral, and social patterns that enable realistic simulation of how the subject communicates, how different audience segments think, react, interact, and make decisions."
# # # ]

# # # detailed_guidelines = [
# # #     "Do not write a conventional biography.",
# # #     "The primary objective is to build a Digital Twin of the subject and the audience ecosystem surrounding them.",
# # #     "Treat the subject as an influence source and the audience as the primary system being modeled.",
# # #     "Prioritize structured knowledge extraction over narrative writing.",
# # #     "Identify recurring behavioral, ideological, cultural, communicative, and social patterns rather than isolated events.",
# # #     "Extract reusable knowledge suitable for behavioral simulation rather than descriptive summaries.",
# # #     "Reverse engineer the subject's worldview, ideology, epistemology, philosophy, methodology, and system of thought.",
# # #     "Identify the beliefs, values, assumptions, priorities, and recurring principles that consistently shape the subject's discourse.",
# # #     "Determine which ideas define the subject's public identity and which themes dominate their communication.",
# # #     "Analyze how the subject justifies truth, authority, evidence, morality, religion, politics, society, identity, and social order.",
# # #     "Carefully analyze ideological characteristics supported by evidence, including conservatism, liberalism, progressivism, nationalism, populism, sectarianism, exclusivism, traditionalism, reformism, political mobilization, religious fundamentalism, extremism, discrimination, conspiracy narratives, or similar recurring patterns whenever applicable.",
# # #     "Do not assign ideological labels unless supported by multiple independent pieces of evidence.",
# # #     "Carefully analyze the subject's positions regarding religion, politics, democracy, secularism, women, gender roles, minorities, human rights, violence, extremism, education, social norms, and other major societal issues whenever sufficient evidence exists.",
# # #     "Identify which ideas generate the strongest support, criticism, polarization, or controversy.",
# # #     "Treat the audience as a complex social system rather than a list of followers.",
# # #     "Identify audience demographics, ideological tendencies, education, geography, religiosity, socioeconomic characteristics, motivations, and cultural background whenever evidence exists.",
# # #     "Reverse engineer why different audience groups trust, reject, defend, or criticize the subject.",
# # #     "Analyze audience values, identities, fears, aspirations, moral intuitions, and cultural assumptions whenever observable evidence exists.",
# # #     "Analyze how different audience segments react to specific ideas rather than only measuring engagement.",
# # #     "Identify which ideas resonate most strongly with which communities and explain why.",
# # #     "Analyze disagreement inside the audience whenever multiple communities interpret the subject differently.",
# # #     "Analyze how ideas spread through books, lectures, institutions, YouTube, television, social media, personal networks, communities, organizations, and other dissemination mechanisms.",
# # #     "Explain the interaction between ideology, communication style, audience composition, dissemination channels, and observable influence rather than describing each independently.",
# # #     "Analyze rhetorical style, framing strategies, narratives, symbolism, emotional appeals, authority construction, persuasive techniques, storytelling, and educational methods.",
# # #     "Identify recurring messaging patterns and communication strategies.",
# # #     "Map important allies, critics, competing schools of thought, rival influencers, institutions, organizations, media ecosystems, and communities interacting with the subject."
# # # ]


# # # # ============================================================
# # # # MAIN FUNCTION
# # # # ============================================================

# # # async def run_research_experiment():
    
# # #     subject_name = "Sheikh Mostafa Al-Adawy"
# # #     website_url = "https://mostafaaladwy.com"
# # #     short_description = "An Egyptian Salafi Islamic scholar, hadith specialist, and contemporary religious influencer shaping public discourse through books, lectures, and online media."

# # #     user_details = f"""
# # # Subject: {subject_name}

# # # {short_description}

# # # The subject is a public-facing influencer, media personality, content creator, thought leader, entrepreneur, activist, educator, artist, religious figure, political commentator, expert, or online personality.

# # # The subject has a significant digital presence through platforms such as YouTube, TikTok, Instagram, X/Twitter, Facebook, podcasts, newsletters, websites, online communities, or other communication channels.

# # # The objective is not to create a traditional biography.

# # # The objective is to analyze the ecosystem surrounding this person:

# # # - their audience
# # # - followers
# # # - community structure
# # # - influence mechanisms
# # # - communication patterns
# # # - content strategy
# # # - persuasion methods
# # # - social impact
# # # - digital presence
# # # - audience psychology
# # # - information diffusion patterns

# # # Official website/social media:
# # # {website_url}
# # # """

# # #     # دمج كافة الطبقات بشكل ديناميكي ومنظم
# # #     all_questions_compiled = []
    
# # #     # Epistemic Layer
# # #     all_questions_compiled.append(f"\n### {epistemic_layer['name']} ###")
# # #     all_questions_compiled.append(f"Objective: {epistemic_layer['objective'].strip()}")
# # #     all_questions_compiled.extend(f"- {q}" for q in epistemic_layer['research_questions'])

# # #     # Identity Layer
# # #     all_questions_compiled.append(f"\n### {identity_layer['name']} ###")
# # #     all_questions_compiled.append(f"Objective: {identity_layer['objective'].strip()}")
# # #     all_questions_compiled.extend(f"- {q}" for q in identity_layer['research_questions'])

# # #     # Cognitive Analysis Layer
# # #     all_questions_compiled.append("\n### Analysis Layers: Cognitive Layer ###")
# # #     all_questions_compiled.extend(f"- {q}" for q in analysis_layers['cognitive_layer'])

# # #     # Epistemic Analysis Layer
# # #     all_questions_compiled.append("\n### Analysis Layers: Epistemic Layer ###")
# # #     all_questions_compiled.extend(f"- {q}" for q in analysis_layers['epistemic_layer'])

# # #     # Audience Layer
# # #     all_questions_compiled.append("\n### Audience Layer ###")
# # #     all_questions_compiled.extend(f"- {q}" for q in audience_layer)

# # #     # Network Diffusion Layer
# # #     all_questions_compiled.append("\n### Network Diffusion Layer ###")
# # #     all_questions_compiled.extend(f"- {q}" for q in network_diffusion_layer)

# # #     # Influence Layer
# # #     all_questions_compiled.append("\n### Influence Layer ###")
# # #     all_questions_compiled.extend(f"- {q}" for q in influence_layer)

# # #     # Simulation Layer
# # #     all_questions_compiled.append("\n### Simulation Layer ###")
# # #     all_questions_compiled.extend(f"- {q}" for q in simulation_layer)

# # #     # Core Research Questions
# # #     all_questions_compiled.append("\n### Core Research & Digital Twin Extraction ###")
# # #     all_questions_compiled.extend(f"- {q}" for q in research_questions)

# # #     # تكوين الـ Query بالاعتماد على الهيكل المجمّع
# # #     query_parts = [
# # #         "Research Ecosystem and Digital Twin Profile",
# # #         "",
# # #         "Research the following subject:",
# # #         "",
# # #         user_details,
# # #         "",
# # #         "The objective is to construct a comprehensive Digital Twin profile of the audience ecosystem surrounding this subject.",
# # #         "",
# # #         "Additionally, place particular emphasis on answering the following specific research frameworks:",
# # #         "",
# # #         *all_questions_compiled,
# # #     ]

# # #     full_detailed_query = "\n".join(query_parts)
# # #     short_query = "Research Ecosystem and Digital Twin Profile"

# # #     state: GraphState = {
# # #         "user_initial_query": short_query,
# # #         "chain_input": {
# # #             "query": full_detailed_query,
# # #             "guidelines": detailed_guidelines,
# # #             "follow_guidelines": True,
# # #             "max_sections": 5,
# # #             "verbose": True,
# # #         },
# # #         "profile_candidates": [],
# # #         "research_iteration": 0,
# # #     }

# # #     print("⏳ Running live multi-agent research call, please wait...")
# # #     result = await make_research(state)

# # #     candidate = result["profile_candidates"][0]

# # #     print("\nREPORT LENGTH:", len(candidate["full_report"]))
# # #     print("SOURCES:", len(candidate["sources"]))
# # #     print("COSTS:", candidate["costs"])

# # #     with open("multi_agent_test_report.md", "w", encoding="utf-8") as f:
# # #         f.write(candidate["full_report"])

# # #     print("\n✅ Saved: multi_agent_test_report.md")


# # # if __name__ == "__main__":
# # #     asyncio.run(run_research_experiment())



# # # import call_model_loud_patch    # 3. يفضح الـ None بدل ما يخفيها
# # # import ReviserAgentPatch        # 4. شبكة أمان أخيرة
# # # import asyncio
# # # from dotenv import load_dotenv

# # # from Nodes.GPT_ResearcherNode.ResearchNode import make_research
# # # from StateGraph import GraphState

# # # load_dotenv()

# # # # ============================================================
# # # # FIVE ANALYSIS LAYERS (Compact & Focused)
# # # # ============================================================

# # # identity_worldview_layer = {
# # #     "name": "Identity & Worldview Layer",
# # #     "objective": "Establish the subject's public identity, fundamental worldview, and epistemological framework.",
# # #     "extraction_tasks": [
# # #         "Identify the subject's core biographical foundation, key milestones, and historical context.",
# # #         "Extract the subject's fundamental worldview, core beliefs, and hierarchy of values.",
# # #         "Identify the primary knowledge sources and authorities relied upon.",
# # #         "Analyze the epistemological methodology used to evaluate evidence and justify truth claims.",
# # #         "Extract the primary cognitive models and reasoning patterns used to explain complex societal issues.",
# # #         "Identify consistent ideological characteristics and positions on major social, political, or religious issues.",
# # #         "Explain how different ideas connect into one internally coherent belief system."
# # #     ]
# # # }

# # # audience_community_layer = {
# # #     "name": "Audience & Community Layer",
# # #     "objective": "Understand who composes the audience, why they participate, how communities form, and how engagement evolves over time.",
# # #     "extraction_tasks": [
# # #         "Identify the major audience segments and characterize them by demographics, education, and socioeconomic background.",
# # #         "Explain why each segment is attracted to the subject, what psychological needs are fulfilled, and how engagement differs across groups.",
# # #         "Extract the shared cultural norms, moral priorities, identity markers, and assumptions characterizing the audience ecosystem.",
# # #         "Identify formal and informal community structures, influential followers, and secondary influencers.",
# # #         "Determine how trust develops, how newcomers integrate, and how long-term members differ from casual consumers.",
# # #         "Analyze how disagreement, controversy, or conflicting interpretations are handled within the community.",
# # #         "Extract shared language, terminology, symbols, and recurring narratives used by followers."
# # #     ]
# # # }

# # # influence_diffusion_layer = {
# # #     "name": "Influence & Diffusion Layer",
# # #     "objective": "Map how ideas move from the subject into the wider ecosystem and measure observable impact.",
# # #     "extraction_tasks": [
# # #         "Map the complete diffusion chain from the original message to wider public adoption.",
# # #         "Identify key intermediaries, institutions, and platforms that accelerate or filter the spread of ideas.",
# # #         "Explain how information flows and identify self-reinforcing feedback loops between the subject and the audience.",
# # #         "Identify which concepts or frameworks have been adopted, cited, or debated beyond the immediate audience.",
# # #         "Extract observable evidence of the subject's influence on social behavior, community cohesion, or public discourse.",
# # #         "Identify factors that strengthen long-term influence versus ideas that fail to spread.",
# # #         "Analyze how the ecosystem interacts with competitors, critics, and alternative schools of thought."
# # #     ]
# # # }

# # # mechanistic_layer = {
# # #     "name": "Mechanistic Intelligence Layer",
# # #     "objective": "Extract the specific mechanisms through which influence, trust, and behavioral changes occur.",
# # #     "extraction_tasks": [
# # #         "Extract recurring cognitive biases and mental shortcuts utilized within the ecosystem.",
# # #         "Extract recurring argument structures and framing mechanisms.",
# # #         "Extract specific persuasion mechanisms, rhetorical strategies, and emotional triggers.",
# # #         "Extract mechanisms for trust formation and authority recognition.",
# # #         "Extract mechanisms for conflict resolution and polarization.",
# # #         "Identify the specific conditions that reliably increase or decrease the subject's influence."
# # #     ]
# # # }

# # # simulation_layer = {
# # #     "name": "Simulation Extraction Layer",
# # #     "objective": "Produce structured outputs necessary for initializing an agent-based computational Digital Twin.",
# # #     "extraction_tasks": [
# # #         "Produce reusable IF-THEN behavioral rules.",
# # #         "Extract highly stable beliefs versus context-dependent opinions.",
# # #         "Extract decision-making rules and heuristics.",
# # #         "Extract trust mechanisms.",
# # #         "Extract communication patterns and stylistic rules.",
# # #         "Extract likely reactions to common events (e.g., praise, criticism, controversy).",
# # #         "Identify all critical variables required for an agent-based simulation."
# # #     ]
# # # }

# # # # ============================================================
# # # # COMPACT GUIDELINES (Evidence & Mindset)
# # # # ============================================================

# # # detailed_guidelines = [
# # #     "EVIDENCE FIRST: Collect sufficient evidence from diverse sources before attempting analysis. Rely on observations of audience behavior, not just the subject's claims.",
# # #     "EXTRACT, DO NOT DESCRIBE: Prioritize structured knowledge extraction (patterns, mechanisms, rules) over chronological narrative or descriptive text.",
# # #     "NO SPECULATION: Clearly distinguish behaviors supported by strong evidence from reasonable analytical inferences. Identify important knowledge gaps.",
# # #     "CAUSAL FOCUS: Explain the relationship between the subject's ideas, audience composition, communication style, and observed influence.",
# # #     "DATA STRUCTURE: Format the final output to support the immediate construction of computational models and simulations."
# # # ]

# # # # ============================================================
# # # # HELPER FUNCTIONS
# # # # ============================================================

# # # def add_layer(target, layer):
# # #     """
# # #     Helper function to cleanly append a research layer into the query structure.
# # #     """
# # #     target.append(f"\n### {layer['name']}")
# # #     if "objective" in layer and layer["objective"]:
# # #         target.append(f"Objective: {layer['objective'].strip()}")
    
# # #     if "extraction_tasks" in layer:
# # #         target.append("Extraction Tasks:")
# # #         target.extend(f"- {q}" for q in layer["extraction_tasks"])

# # # # ============================================================
# # # # MAIN FUNCTION
# # # # ============================================================

# # # async def run_research_experiment():
    
# # #     subject_name = "Sheikh Mostafa Al-Adawy"
# # #     website_url = "https://mostafaaladwy.com"
# # #     short_description = "An Egyptian Salafi Islamic scholar, hadith specialist, and contemporary religious influencer."

# # #     # 1. Compact User Details
# # #     user_details = f"""
# # # Subject: {subject_name}

# # # {short_description}

# # # A prominent public figure with a substantial online presence whose ideas are disseminated through books, lectures, interviews, websites, YouTube, and other digital platforms.

# # # Official website:
# # # {website_url}
# # # """

# # #     # 2. Master Directives & Research Goal
# # #     master_directives = [
# # #         "Digital Twin Reverse Engineering",
# # #         "",
# # #         "CRITICAL DIRECTIVE: The primary deliverable is not descriptive text.",
# # #         "The primary deliverable is a structured knowledge model that explains how the ecosystem functions and can later be used to construct computational Digital Twins and agent-based simulations.",
# # #         "",
# # #         "Goal: Build an evidence-based Digital Twin of the subject's intellectual ecosystem rather than a traditional biography.",
# # #         "",
# # #         "Subject Overview:",
# # #         user_details.strip(),
# # #         ""
# # #     ]

# # #     query_parts = list(master_directives)

# # #     # 3. Injecting the 5 Focused Layers
# # #     add_layer(query_parts, identity_worldview_layer)
# # #     add_layer(query_parts, audience_community_layer)
# # #     add_layer(query_parts, influence_diffusion_layer)
# # #     add_layer(query_parts, mechanistic_layer)
# # #     add_layer(query_parts, simulation_layer)

# # #     full_detailed_query = "\n".join(query_parts)
# # #     short_query = "Digital Twin Reverse Engineering"

# # #     state: GraphState = {
# # #         "user_initial_query": short_query,
# # #         "chain_input": {
# # #             "query": full_detailed_query,
# # #             "guidelines": detailed_guidelines,
# # #             "follow_guidelines": True,
# # #             "max_sections": 5,
# # #             "verbose": True,
# # #         },
# # #         "profile_candidates": [],
# # #         "research_iteration": 0,
# # #     }

# # #     print("⏳ Running streamlined multi-agent intelligence profiling, please wait...")
# # #     result = await make_research(state)

# # #     candidate = result["profile_candidates"][0]

# # #     print("\nREPORT LENGTH:", len(candidate["full_report"]))
# # #     print("SOURCES:", len(candidate["sources"]))
# # #     print("COSTS:", candidate["costs"])

# # #     with open("multi_agent_test_report.md", "w", encoding="utf-8") as f:
# # #         f.write(candidate["full_report"])

# # #     print("\n✅ Saved: multi_agent_test_report.md")


# # # if __name__ == "__main__":
# # #     asyncio.run(run_research_experiment())



# # import call_model_loud_patch    # 3. يفضح الـ None بدل ما يخفيها
# # import ReviserAgentPatch        # 4. شبكة أمان أخيرة
# # import asyncio
# # from dotenv import load_dotenv

# # from Nodes.GPT_ResearcherNode.ResearchNode import make_research
# # from StateGraph import GraphState

# # load_dotenv()

# # # ============================================================
# # # FIVE ANALYSIS LAYERS (Compact & Focused)
# # # ============================================================

# # identity_worldview_layer = {
# #     "name": "Identity & Worldview Layer",
# #     "objective": "Establish the subject's public identity, fundamental worldview, and epistemological framework.",
# #     "extraction_tasks": [
# #         "Identify the subject's core biographical foundation, key milestones, and historical context.",
# #         "Extract the subject's fundamental worldview, core beliefs, and hierarchy of values.",
# #         "Identify the primary knowledge sources and authorities relied upon.",
# #         "Analyze the epistemological methodology used to evaluate evidence and justify truth claims.",
# #         "Extract the primary cognitive models and reasoning patterns used to explain complex societal issues.",
# #         "Identify consistent ideological characteristics and positions on major social, political, or religious issues.",
# #         "Explain how different ideas connect into one internally coherent belief system."
# #     ]
# # }

# # audience_community_layer = {
# #     "name": "Audience & Community Layer",
# #     "objective": "Understand who composes the audience, why they participate, how communities form, and how engagement evolves over time.",
# #     "extraction_tasks": [
# #         "Identify the major audience segments and characterize them by demographics, education, and socioeconomic background.",
# #         "Explain why each segment is attracted to the subject, what psychological needs are fulfilled, and how engagement differs across groups.",
# #         "Extract the shared cultural norms, moral priorities, identity markers, and assumptions characterizing the audience ecosystem.",
# #         "Identify formal and informal community structures, influential followers, and secondary influencers.",
# #         "Determine how trust develops, how newcomers integrate, and how long-term members differ from casual consumers.",
# #         "Analyze how disagreement, controversy, or conflicting interpretations are handled within the community.",
# #         "Extract shared language, terminology, symbols, and recurring narratives used by followers."
# #     ]
# # }

# # influence_diffusion_layer = {
# #     "name": "Influence & Diffusion Layer",
# #     "objective": "Map how ideas move from the subject into the wider ecosystem and measure observable impact.",
# #     "extraction_tasks": [
# #         "Map the complete diffusion chain from the original message to wider public adoption.",
# #         "Identify key intermediaries, institutions, and platforms that accelerate or filter the spread of ideas.",
# #         "Explain how information flows and identify self-reinforcing feedback loops between the subject and the audience.",
# #         "Identify which concepts or frameworks have been adopted, cited, or debated beyond the immediate audience.",
# #         "Extract observable evidence of the subject's influence on social behavior, community cohesion, or public discourse.",
# #         "Identify factors that strengthen long-term influence versus ideas that fail to spread.",
# #         "Analyze how the ecosystem interacts with competitors, critics, and alternative schools of thought."
# #     ]
# # }

# # mechanistic_layer = {
# #     "name": "Mechanistic Intelligence Layer",
# #     "objective": "Extract the specific mechanisms through which influence, trust, and behavioral changes occur.",
# #     "extraction_tasks": [
# #         "Extract recurring cognitive biases and mental shortcuts utilized within the ecosystem.",
# #         "Extract recurring argument structures and framing mechanisms.",
# #         "Extract specific persuasion mechanisms, rhetorical strategies, and emotional triggers.",
# #         "Extract mechanisms for trust formation and authority recognition.",
# #         "Extract mechanisms for conflict resolution and polarization.",
# #         "Identify the specific conditions that reliably increase or decrease the subject's influence."
# #     ]
# # }

# # simulation_layer = {
# #     "name": "Simulation Extraction Layer",
# #     "objective": "Produce structured outputs necessary for initializing an agent-based computational Digital Twin.",
# #     "extraction_tasks": [
# #         "Produce reusable IF-THEN behavioral rules.",
# #         "Extract highly stable beliefs versus context-dependent opinions.",
# #         "Extract decision-making rules and heuristics.",
# #         "Extract trust mechanisms.",
# #         "Extract communication patterns and stylistic rules.",
# #         "Extract likely reactions to common events (e.g., praise, criticism, controversy).",
# #         "Identify all critical variables required for an agent-based simulation."
# #     ]
# # }

# # # ============================================================
# # # COMPACT GUIDELINES (Evidence & Mindset)
# # # ============================================================

# # detailed1_guidelines = [
# #     "EVIDENCE FIRST: Collect sufficient evidence from diverse sources before attempting analysis. Rely on observations of audience behavior, not just the subject's claims.",
# #     "EXTRACT, DO NOT DESCRIBE: Prioritize structured knowledge extraction (patterns, mechanisms, rules) over chronological narrative or descriptive text.",
# #     "NO SPECULATION: Clearly distinguish behaviors supported by strong evidence from reasonable analytical inferences. Identify important knowledge gaps.",
# #     "CAUSAL FOCUS: Explain the relationship between the subject's ideas, audience composition, communication style, and observed influence.",
# #     "DATA STRUCTURE: Format the final output to support the immediate construction of computational models and simulations."
# # ]


# # detailed2_guidelines = [
# #     "Do not write a conventional biography.",
# #     "The primary objective is to build a Digital Twin of the subject and the audience ecosystem surrounding them.",
# #     "Treat the subject as an influence source and the audience as the primary system being modeled.",
# #     "Prioritize structured knowledge extraction over narrative writing.",
# #     "Identify recurring behavioral, ideological, cultural, communicative, and social patterns rather than isolated events.",
# #     "Extract reusable knowledge suitable for behavioral simulation rather than descriptive summaries.",
# #     "Reverse engineer the subject's worldview, ideology, epistemology, philosophy, methodology, and system of thought.",
# #     "Identify the beliefs, values, assumptions, priorities, and recurring principles that consistently shape the subject's discourse.",
# #     "Determine which ideas define the subject's public identity and which themes dominate their communication.",
# #     "Analyze how the subject justifies truth, authority, evidence, morality, religion, politics, society, identity, and social order.",
# #     "Carefully analyze ideological characteristics supported by evidence, including conservatism, liberalism, progressivism, nationalism, populism, sectarianism, exclusivism, traditionalism, reformism, political mobilization, religious fundamentalism, extremism, discrimination, conspiracy narratives, or similar recurring patterns whenever applicable.",
# #     "Do not assign ideological labels unless supported by multiple independent pieces of evidence.",
# #     "Carefully analyze the subject's positions regarding religion, politics, democracy, secularism, women, gender roles, minorities, human rights, violence, extremism, education, social norms, and other major societal issues whenever sufficient evidence exists.",
# #     "Identify which ideas generate the strongest support, criticism, polarization, or controversy.",
# #     "Treat the audience as a complex social system rather than a list of followers.",
# #     "Identify audience demographics, ideological tendencies, education, geography, religiosity, socioeconomic characteristics, motivations, and cultural background whenever evidence exists.",
# #     "Reverse engineer why different audience groups trust, reject, defend, or criticize the subject.",
# #     "Analyze audience values, identities, fears, aspirations, moral intuitions, and cultural assumptions whenever observable evidence exists.",
# #     "Analyze how different audience segments react to specific ideas rather than only measuring engagement.",
# #     "Identify which ideas resonate most strongly with which communities and explain why.",
# #     "Analyze disagreement inside the audience whenever multiple communities interpret the subject differently.",
# #     "Analyze how ideas spread through books, lectures, institutions, YouTube, television, social media, personal networks, communities, organizations, and other dissemination mechanisms.",
# #     "Explain the interaction between ideology, communication style, audience composition, dissemination channels, and observable influence rather than describing each independently.",
# #     "Analyze rhetorical style, framing strategies, narratives, symbolism, emotional appeals, authority construction, persuasive techniques, storytelling, and educational methods.",
# #     "Identify recurring messaging patterns and communication strategies.",
# #     "Map important allies, critics, competing schools of thought, rival influencers, institutions, organizations, media ecosystems, and communities interacting with the subject."
# # ]


# # detailed_guidelines = detailed1_guidelines + detailed2_guidelines
# # # ============================================================
# # # HELPER FUNCTIONS
# # # ============================================================

# # def add_layer(target, layer):
# #     """
# #     Helper function to cleanly append a research layer into the query structure.
# #     """
# #     target.append(f"\n### {layer['name']}")
# #     if "objective" in layer and layer["objective"]:
# #         target.append(f"Objective: {layer['objective'].strip()}")
    
# #     if "extraction_tasks" in layer:
# #         target.append("Extraction Tasks:")
# #         target.extend(f"- {q}" for q in layer["extraction_tasks"])

# # # ============================================================
# # # MAIN FUNCTION
# # # ============================================================

# # async def run_research_experiment():
    
# #     subject_name = "Sheikh Mostafa Al-Adawy"
# #     website_url = "https://mostafaaladwy.com"
# #     short_description = "An Egyptian Salafi Islamic scholar, hadith specialist, and contemporary religious influencer."

# #     # 1. Compact User Details
# #     user_details = f"""
# # Subject: {subject_name}

# # {short_description}

# # A prominent public figure with a substantial online presence whose ideas are disseminated through books, lectures, interviews, websites, YouTube, and other digital platforms.

# # Official website:
# # {website_url}
# # """

# #     # 2. Master Directives & Research Goal
# #     master_directives = [
# #         "Digital Twin Reverse Engineering",
# #         "",
# #         "CRITICAL DIRECTIVE: The primary deliverable is not descriptive text.",
# #         "The primary deliverable is a structured knowledge model that explains how the ecosystem functions and can later be used to construct computational Digital Twins and agent-based simulations.",
# #         "",
# #         "Goal: Build an evidence-based Digital Twin of the subject's intellectual ecosystem rather than a traditional biography.",
# #         "",
# #         "Subject Overview:",
# #         user_details.strip(),
# #         ""
# #     ]

# #     query_parts = list(master_directives)

# #     # 3. Injecting the 5 Focused Layers
# #     add_layer(query_parts, identity_worldview_layer)
# #     add_layer(query_parts, audience_community_layer)
# #     add_layer(query_parts, influence_diffusion_layer)
# #     add_layer(query_parts, mechanistic_layer)
# #     add_layer(query_parts, simulation_layer)

# #     full_detailed_query = "\n".join(query_parts)
# #     short_query = "Digital Twin Reverse Engineering"

# #     state: GraphState = {
# #         "user_initial_query": short_query,
# #         "chain_input": {
# #             "query": full_detailed_query,
# #             "guidelines": detailed_guidelines,
# #             "follow_guidelines": True,
# #             "max_sections": 5,
# #             "verbose": True,
# #         },
# #         "profile_candidates": [],
# #         "research_iteration": 0,
# #     }

# #     print("⏳ Running streamlined multi-agent intelligence profiling, please wait...")
# #     result = await make_research(state)

# #     candidate = result["profile_candidates"][0]

# #     print("\nREPORT LENGTH:", len(candidate["full_report"]))
# #     print("SOURCES:", len(candidate["sources"]))
# #     print("COSTS:", candidate["costs"])

# #     with open("multi_agent_test_report.md", "w", encoding="utf-8") as f:
# #         f.write(candidate["full_report"])

# #     print("\n✅ Saved: multi_agent_test_report.md")


# # if __name__ == "__main__":
# #     asyncio.run(run_research_experiment())
# # import call_model_loud_patch    # 3. يفضح الـ None بدل ما يخفيها
# # import ReviserAgentPatch        # 4. شبكة أمان أخيرة
# # import asyncio
# # from dotenv import load_dotenv

# # from Nodes.GPT_ResearcherNode.ResearchNode import make_research
# # from StateGraph import GraphState

# # load_dotenv()

# # # ============================================================
# # # FIVE ANALYSIS LAYERS (Compact & Focused)
# # # ============================================================

# # identity_worldview_layer = {
# #     "name": "Identity & Worldview Layer",
# #     "objective": "Establish the subject's public identity, fundamental worldview, and epistemological framework.",
# #     "extraction_tasks": [
# #         "Identify the subject's core biographical foundation, key milestones, and historical context.",
# #         "Extract the subject's fundamental worldview, core beliefs, and hierarchy of values.",
# #         "Identify the primary knowledge sources and authorities relied upon.",
# #         "Analyze the epistemological methodology used to evaluate evidence and justify truth claims.",
# #         "Extract the primary cognitive models and reasoning patterns used to explain complex societal issues.",
# #         "Identify consistent ideological characteristics and positions on major social, political, or religious issues.",
# #         "Explain how different ideas connect into one internally coherent belief system."
# #     ]
# # }

# # audience_community_layer = {
# #     "name": "Audience & Community Layer",
# #     "objective": "Understand who composes the audience, why they participate, how communities form, and how engagement evolves over time.",
# #     "extraction_tasks": [
# #         "Identify the major audience segments and characterize them by demographics, education, and socioeconomic background.",
# #         "Explain why each segment is attracted to the subject, what psychological needs are fulfilled, and how engagement differs across groups.",
# #         "Extract the shared cultural norms, moral priorities, identity markers, and assumptions characterizing the audience ecosystem.",
# #         "Identify formal and informal community structures, influential followers, and secondary influencers.",
# #         "Determine how trust develops, how newcomers integrate, and how long-term members differ from casual consumers.",
# #         "Analyze how disagreement, controversy, or conflicting interpretations are handled within the community.",
# #         "Extract shared language, terminology, symbols, and recurring narratives used by followers."
# #     ]
# # }

# # discourse_layer = {
# #     "name": "Discourse & Communication Layer",
# #     "objective": "Reverse engineer how the subject communicates and how ideas are framed.",
# #     "extraction_tasks": [
# #         "Identify recurring narratives, frames, metaphors, and messaging patterns.",
# #         "Extract rhetorical, educational, emotional, and persuasive techniques.",
# #         "Explain how complex issues are simplified for different audiences.",
# #         "Identify recurring authority-building strategies and legitimacy signals.",
# #         "Determine which communication styles generate the strongest audience response."
# #     ]
# # }



# # ideas_ideology_layer = {
# #     "name": "Ideas & Ideology Layer",
# #     "objective": "Reverse engineer the subject's intellectual architecture, ideology, value system, and major ideas.",

# #     "extraction_tasks": [
# #         "Identify the subject's most influential ideas and recurring intellectual themes.",
# #         "Extract the core belief system, worldview, and hierarchy of values.",
# #         "Identify ideological positions supported by evidence on religion, politics, society, gender, identity, morality, education, economics, and other major issues.",
# #         "Distinguish central beliefs from secondary opinions.",
# #         "Identify recurring assumptions about human nature, authority, social order, justice, tradition, and change.",
# #         "Explain how different beliefs connect into one internally coherent ideological framework.",
# #         "Identify which ideas generate the strongest support, criticism, or controversy.",
# #         "Extract ideas that appear essential for maintaining audience cohesion."
# #     ]
# # }

# # epistemology_layer = {
# #     "name": "Epistemology & Reasoning Layer",
# #     "objective": "Understand how the subject evaluates knowledge, evidence, and truth.",

# #     "extraction_tasks": [
# #         "Identify the primary sources of authority used to justify claims.",
# #         "Analyze how evidence is evaluated and prioritized.",
# #         "Extract recurring reasoning patterns and decision frameworks.",
# #         "Identify recurring cognitive models used to explain complex issues.",
# #         "Analyze how uncertainty, disagreement, and ambiguity are handled.",
# #         "Explain how the subject constructs credibility and legitimacy."
# #     ]
# # }

# # narrative_communication_layer = {
# #     "name": "Narrative & Communication Layer",
# #     "objective": "Reverse engineer how the subject communicates ideas, persuades audiences, and transforms beliefs into narratives that spread across communities.",

# #     "extraction_tasks": [
# #         "Identify the subject's dominant communication style and recurring rhetorical patterns.",
# #         "Extract recurring narratives, frames, slogans, metaphors, symbols, and storytelling techniques.",
# #         "Analyze how complex ideas are simplified and adapted for different audiences.",
# #         "Identify recurring emotional appeals, persuasive strategies, and methods of audience engagement.",
# #         "Analyze how authority, credibility, legitimacy, and expertise are communicated and reinforced.",
# #         "Identify recurring linguistic patterns, terminology, catchphrases, and stylistic characteristics.",
# #         "Explain how controversial topics are framed and how competing viewpoints are represented.",
# #         "Analyze how communication strategies evolve across books, lectures, interviews, videos, social media, and other communication channels.",
# #         "Identify which communication patterns generate the strongest engagement, trust, controversy, or long-term influence.",
# #         "Extract reusable communication and persuasion patterns suitable for behavioral simulation."
# #     ]
# # }

# # controversy_layer = {
# #     "name": "Controversy & Polarization Layer",
# #     "objective": "Understand disagreement, competing narratives, and ecosystem conflicts.",
# #     "extraction_tasks": [
# #         "Identify the subject's principal critics, competitors, and rival schools of thought.",
# #         "Explain the main causes of disagreement and ideological conflict.",
# #         "Analyze which ideas generate the strongest support, criticism, or polarization.",
# #         "Identify recurring counter-narratives and competing interpretations.",
# #         "Explain how supporters and critics respond differently to the same events."
# #     ]
# # }


# # influence_diffusion_layer = {
# #     "name": "Influence & Diffusion Layer",
# #     "objective": "Map how ideas move from the subject into the wider ecosystem and measure observable impact.",
# #     "extraction_tasks": [
# #         "Map the complete diffusion chain from the original message to wider public adoption.",
# #         "Identify key intermediaries, institutions, and platforms that accelerate or filter the spread of ideas.",
# #         "Explain how information flows and identify self-reinforcing feedback loops between the subject and the audience.",
# #         "Identify which concepts or frameworks have been adopted, cited, or debated beyond the immediate audience.",
# #         "Extract observable evidence of the subject's influence on social behavior, community cohesion, or public discourse.",
# #         "Identify factors that strengthen long-term influence versus ideas that fail to spread.",
# #         "Analyze how the ecosystem interacts with competitors, critics, and alternative schools of thought."
# #     ]
# # }

# # mechanistic_layer = {
# #     "name": "Mechanistic Intelligence Layer",
# #     "objective": "Extract the specific mechanisms through which influence, trust, and behavioral changes occur.",
# #     "extraction_tasks": [
# #         "Extract recurring cognitive biases and mental shortcuts utilized within the ecosystem.",
# #         "Extract recurring argument structures and framing mechanisms.",
# #         "Extract specific persuasion mechanisms, rhetorical strategies, and emotional triggers.",
# #         "Extract mechanisms for trust formation and authority recognition.",
# #         "Extract mechanisms for conflict resolution and polarization.",
# #         "Identify the specific conditions that reliably increase or decrease the subject's influence."
# #     ]
# # }

# # simulation_layer = {
# #     "name": "Simulation Extraction Layer",
# #     "objective": (
# #         "Extract the structured knowledge required to simulate the audience ecosystem "
# #         "surrounding the subject, including how community members think, interact, "
# #         "respond to the subject's ideas, influence one another, and evolve over time."
# #     ),
# #     "extraction_tasks": [
# #         "Extract reusable IF-THEN behavioral rules governing audience behavior.",
# #         "Identify stable beliefs, values, identities, and norms shared by different audience segments.",
# #         "Extract decision-making heuristics used when evaluating new information or competing viewpoints.",
# #         "Identify trust formation, credibility assessment, and authority recognition mechanisms.",
# #         "Extract communication styles, discussion patterns, and information-sharing behaviors.",
# #         "Identify typical audience responses to praise, criticism, controversy, ideological conflict, and major external events.",
# #         "Extract interaction rules between different audience segments, supporters, critics, and neutral observers.",
# #         "Identify feedback loops that reinforce, weaken, or transform community beliefs over time.",
# #         "Extract the variables, states, and transition rules required for an agent-based simulation of the ecosystem."
# #     ]
# # }

# # # ============================================================
# # # COMPACT GUIDELINES (Evidence & Mindset)
# # # ============================================================

# # detailed1_guidelines = [
# #     "EVIDENCE FIRST: Collect sufficient evidence from diverse sources before attempting analysis. Rely on observations of audience behavior, not just the subject's claims.",
# #     "EXTRACT, DO NOT DESCRIBE: Prioritize structured knowledge extraction (patterns, mechanisms, rules) over chronological narrative or descriptive text.",
# #     "CAUSAL FOCUS: Explain the relationship between the subject's ideas, audience composition, communication style, and observed influence.",
# # ]

# # detailed2_guidelines = [
# #     "Do not write a conventional biography.",
# #     "The primary objective is to build a Digital Twin of the subject and the audience ecosystem surrounding them.",
# #     "Treat the subject as an influence source and the audience as the primary system being modeled.",
# #     "Prioritize structured knowledge extraction over narrative writing.",
# #     "Identify recurring behavioral, ideological, cultural, communicative, and social patterns rather than isolated events.",
# #     "Extract reusable knowledge suitable for behavioral simulation rather than descriptive summaries.",
# #     "Reverse engineer the subject's worldview, ideology, epistemology, philosophy, methodology, and system of thought.",
# #     "Identify the beliefs, values, assumptions, priorities, and recurring principles that consistently shape the subject's discourse.",
# #     "Determine which ideas define the subject's public identity and which themes dominate their communication.",
# #     "Analyze how the subject justifies truth, authority, evidence, morality, religion, politics, society, identity, and social order.",
# #     "Carefully analyze ideological characteristics supported by evidence, including conservatism, liberalism, progressivism, nationalism, populism, sectarianism, exclusivism, traditionalism, reformism, political mobilization, religious fundamentalism, extremism, discrimination, conspiracy narratives, or similar recurring patterns whenever applicable.",
# #     "Do not assign ideological labels unless supported by multiple independent pieces of evidence.",
# #     "Carefully analyze the subject's positions regarding religion, politics, democracy, secularism, women, gender roles, minorities, human rights, violence, extremism, education, social norms, and other major societal issues whenever sufficient evidence exists.",
# #     "Identify which ideas generate the strongest support, criticism, polarization, or controversy.",
# #     "Treat the audience as a complex social system rather than a list of followers.",
# #     "Identify audience demographics, ideological tendencies, education, geography, religiosity, socioeconomic characteristics, motivations, and cultural background whenever evidence exists.",
# #     "Reverse engineer why different audience groups trust, reject, defend, or criticize the subject.",
# #     "Analyze audience values, identities, fears, aspirations, moral intuitions, and cultural assumptions whenever observable evidence exists.",
# #     "Analyze how different audience segments react to specific ideas rather than only measuring engagement.",
# #     "Identify which ideas resonate most strongly with which communities and explain why.",
# #     "Analyze disagreement inside the audience whenever multiple communities interpret the subject differently.",
# #     "Analyze how ideas spread through books, lectures, institutions, YouTube, television, social media, personal networks, communities, organizations, and other dissemination mechanisms.",
# #     "Explain the interaction between ideology, communication style, audience composition, dissemination channels, and observable influence rather than describing each independently.",
# #     "Analyze rhetorical style, framing strategies, narratives, symbolism, emotional appeals, authority construction, persuasive techniques, storytelling, and educational methods.",
# #     "Identify recurring messaging patterns and communication strategies.",
# #     "Map important allies, critics, competing schools of thought, rival influencers, institutions, organizations, media ecosystems, and communities interacting with the subject."
# # ]

# # detailed_guidelines = detailed1_guidelines + detailed2_guidelines

# # # ============================================================
# # # HELPER FUNCTIONS
# # # ============================================================

# # def add_layer(target, layer):
# #     """
# #     Helper function to cleanly append a research layer into the query structure.
# #     """
# #     target.append(f"\n### {layer['name']}")
# #     if "objective" in layer and layer["objective"]:
# #         target.append(f"Objective: {layer['objective'].strip()}")
    
# #     if "extraction_tasks" in layer:
# #         target.append("Extraction Tasks:")
# #         target.extend(f"- {q}" for q in layer["extraction_tasks"])

# # # ============================================================
# # # MAIN FUNCTION
# # # ============================================================

# # async def run_research_experiment():
    
# #     subject_name = "Sheikh Mostafa Al-Adawy"
# #     website_url = "https://mostafaaladwy.com"
# #     short_description = "An Egyptian Salafi Islamic scholar, hadith specialist, and contemporary religious influencer."

# #     # 1. Compact User Details
# #     user_details = f"""
# # Subject: {subject_name}

# # {short_description}

# # A prominent public figure with a substantial online presence whose ideas are disseminated through books, lectures, interviews, websites, YouTube, and other digital platforms.

# # Official website:
# # {website_url}
# # """

# #     # 2. Master Directives & Research Goal
# #     master_directives = [
# #     "Research Target: Ecosystem Reverse Engineering",
# #     "",
# #     "The subject is the observation target, not the final product.",
# #     "",
# #     "Reverse engineer the complete ecosystem surrounding the subject, including ideology, communication, audience formation, community dynamics, influence mechanisms, diffusion pathways, and behavioral patterns.",
# #     "",
# #     "Produce structured knowledge suitable for building computational Digital Twin and agent-based simulation models.",
# #     "",
# #     "Prioritize mechanisms over descriptions, causal relationships over isolated facts, and reusable behavioral models over narrative summaries.",
# #     "",
# #     "Subject Overview:",
# #     user_details.strip(),
# #     ""
# # ]

# #     query_parts = list(master_directives)

# #     # 3. Injecting the 5 Focused Layers
# #     add_layer(query_parts, identity_worldview_layer)
# #     add_layer(query_parts, audience_community_layer)
# #     add_layer(query_parts, influence_diffusion_layer)
# #     add_layer(query_parts, mechanistic_layer)
# #     add_layer(query_parts, simulation_layer)

# #     full_detailed_query = "\n".join(query_parts)
    
# #     # رجعنا الكويري الكبيرة بتاعتك زي ما كانت عشان الـ Agent يشتغل صح 100%
# #     state: GraphState = {
# #         "user_initial_query": full_detailed_query, 
# #         "chain_input": {
# #             "query": full_detailed_query,
# #             "guidelines": detailed_guidelines,
# #             "follow_guidelines": True,
# #             "max_sections": 5,
# #             "verbose": True,
# #         },
# #         "profile_candidates": [],
# #         "research_iteration": 0,
# #     }

# #     print("⏳ Running streamlined multi-agent intelligence profiling, please wait...")
# #     result = await make_research(state)

# #     candidate = result["profile_candidates"][0]

# #     print("\nREPORT LENGTH:", len(candidate["full_report"]))
# #     print("SOURCES:", len(candidate["sources"]))
# #     print("COSTS:", candidate["costs"])

# #     with open("multi_agent_test_report.md", "w", encoding="utf-8") as f:
# #         f.write(candidate["full_report"])

# #     print("\n✅ Saved: multi_agent_test_report.md")


# # if __name__ == "__main__":
# #     asyncio.run(run_research_experiment())


# import call_model_loud_patch    # 3. يفضح الـ None بدل ما يخفيها
# import ReviserAgentPatch        # 4. شبكة أمان أخيرة
# import asyncio
# from dotenv import load_dotenv

# from Nodes.GPT_ResearcherNode.ResearchNode import make_research
# from StateGraph import GraphState

# load_dotenv()

# # ============================================================
# # ANALYSIS LAYERS (Compact & Focused)
# # ============================================================

# identity_worldview_layer = {
#     "name": "Identity & Worldview Layer",
#     "objective": "Establish the subject's public identity, fundamental worldview, and epistemological framework.",
#     "extraction_tasks": [
#         "Identify the subject's core biographical foundation, key milestones, and historical context.",
#         "Extract the subject's fundamental worldview, core beliefs, and hierarchy of values.",
#         "Identify the primary knowledge sources and authorities relied upon.",
#         "Analyze the epistemological methodology used to evaluate evidence and justify truth claims.",
#         "Extract the primary cognitive models and reasoning patterns used to explain complex societal issues.",
#         "Identify consistent ideological characteristics and positions on major social, political, or religious issues.",
#         "Explain how different ideas connect into one internally coherent belief system."
#     ]
# }

# audience_community_layer = {
#     "name": "Audience & Community Layer",
#     "objective": "Understand who composes the audience, why they participate, how communities form, and how engagement evolves over time.",
#     "extraction_tasks": [
#         "Identify the major audience segments and characterize them by demographics, education, and socioeconomic background.",
#         "Explain why each segment is attracted to the subject, what psychological needs are fulfilled, and how engagement differs across groups.",
#         "Extract the shared cultural norms, moral priorities, identity markers, and assumptions characterizing the audience ecosystem.",
#         "Identify formal and informal community structures, influential followers, and secondary influencers.",
#         "Determine how trust develops, how newcomers integrate, and how long-term members differ from casual consumers.",
#         "Analyze how disagreement, controversy, or conflicting interpretations are handled within the community.",
#         "Extract shared language, terminology, symbols, and recurring narratives used by followers."
#     ]
# }

# discourse_layer = {
#     "name": "Discourse & Communication Layer",
#     "objective": "Reverse engineer how the subject communicates and how ideas are framed.",
#     "extraction_tasks": [
#         "Identify recurring narratives, frames, metaphors, and messaging patterns.",
#         "Extract rhetorical, educational, emotional, and persuasive techniques.",
#         "Explain how complex issues are simplified for different audiences.",
#         "Identify recurring authority-building strategies and legitimacy signals.",
#         "Determine which communication styles generate the strongest audience response."
#     ]
# }

# ideas_ideology_layer = {
#     "name": "Ideas & Ideology Layer",
#     "objective": "Reverse engineer the subject's intellectual architecture, ideology, value system, and major ideas.",
#     "extraction_tasks": [
#         "Identify the subject's most influential ideas and recurring intellectual themes.",
#         "Extract the core belief system, worldview, and hierarchy of values.",
#         "Identify ideological positions supported by evidence on religion, politics, society, gender, identity, morality, education, economics, and other major issues.",
#         "Distinguish central beliefs from secondary opinions.",
#         "Identify recurring assumptions about human nature, authority, social order, justice, tradition, and change.",
#         "Explain how different beliefs connect into one internally coherent ideological framework.",
#         "Identify which ideas generate the strongest support, criticism, or controversy.",
#         "Extract ideas that appear essential for maintaining audience cohesion."
#     ]
# }

# epistemology_layer = {
#     "name": "Epistemology & Reasoning Layer",
#     "objective": "Understand how the subject evaluates knowledge, evidence, and truth.",
#     "extraction_tasks": [
#         "Identify the primary sources of authority used to justify claims.",
#         "Analyze how evidence is evaluated and prioritized.",
#         "Extract recurring reasoning patterns and decision frameworks.",
#         "Identify recurring cognitive models used to explain complex issues.",
#         "Analyze how uncertainty, disagreement, and ambiguity are handled.",
#         "Explain how the subject constructs credibility and legitimacy."
#     ]
# }

# narrative_communication_layer = {
#     "name": "Narrative & Communication Layer",
#     "objective": "Reverse engineer how the subject communicates ideas, persuades audiences, and transforms beliefs into narratives that spread across communities.",
#     "extraction_tasks": [
#         "Identify the subject's dominant communication style and recurring rhetorical patterns.",
#         "Extract recurring narratives, frames, slogans, metaphors, symbols, and storytelling techniques.",
#         "Analyze how complex ideas are simplified and adapted for different audiences.",
#         "Identify recurring emotional appeals, persuasive strategies, and methods of audience engagement.",
#         "Analyze how authority, credibility, legitimacy, and expertise are communicated and reinforced.",
#         "Identify recurring linguistic patterns, terminology, catchphrases, and stylistic characteristics.",
#         "Explain how controversial topics are framed and how competing viewpoints are represented.",
#         "Analyze how communication strategies evolve across books, lectures, interviews, videos, social media, and other communication channels.",
#         "Identify which communication patterns generate the strongest engagement, trust, controversy, or long-term influence.",
#         "Extract reusable communication and persuasion patterns suitable for behavioral simulation."
#     ]
# }

# controversy_layer = {
#     "name": "Controversy & Polarization Layer",
#     "objective": "Understand disagreement, competing narratives, and ecosystem conflicts.",
#     "extraction_tasks": [
#         "Identify the subject's principal critics, competitors, and rival schools of thought.",
#         "Explain the main causes of disagreement and ideological conflict.",
#         "Analyze which ideas generate the strongest support, criticism, or polarization.",
#         "Identify recurring counter-narratives and competing interpretations.",
#         "Explain how supporters and critics respond differently to the same events."
#     ]
# }

# influence_diffusion_layer = {
#     "name": "Influence & Diffusion Layer",
#     "objective": "Map how ideas move from the subject into the wider ecosystem and measure observable impact.",
#     "extraction_tasks": [
#         "Map the complete diffusion chain from the original message to wider public adoption.",
#         "Identify key intermediaries, institutions, and platforms that accelerate or filter the spread of ideas.",
#         "Explain how information flows and identify self-reinforcing feedback loops between the subject and the audience.",
#         "Identify which concepts or frameworks have been adopted, cited, or debated beyond the immediate audience.",
#         "Extract observable evidence of the subject's influence on social behavior, community cohesion, or public discourse.",
#         "Identify factors that strengthen long-term influence versus ideas that fail to spread.",
#         "Analyze how the ecosystem interacts with competitors, critics, and alternative schools of thought."
#     ]
# }

# mechanistic_layer = {
#     "name": "Mechanistic Intelligence Layer",
#     "objective": "Extract the specific mechanisms through which influence, trust, and behavioral changes occur.",
#     "extraction_tasks": [
#         "Extract recurring cognitive biases and mental shortcuts utilized within the ecosystem.",
#         "Extract recurring argument structures and framing mechanisms.",
#         "Extract specific persuasion mechanisms, rhetorical strategies, and emotional triggers.",
#         "Extract mechanisms for trust formation and authority recognition.",
#         "Extract mechanisms for conflict resolution and polarization.",
#         "Identify the specific conditions that reliably increase or decrease the subject's influence."
#     ]
# }

# simulation_layer = {
#     "name": "Simulation Extraction Layer",
#     "objective": (
#         "Extract the structured knowledge required to simulate the audience ecosystem "
#         "surrounding the subject, including how community members think, interact, "
#         "respond to the subject's ideas, influence one another, and evolve over time."
#     ),
#     "extraction_tasks": [
#         "Extract reusable IF-THEN behavioral rules governing audience behavior.",
#         "Identify stable beliefs, values, identities, and norms shared by different audience segments.",
#         "Extract decision-making heuristics used when evaluating new information or competing viewpoints.",
#         "Identify trust formation, credibility assessment, and authority recognition mechanisms.",
#         "Extract communication styles, discussion patterns, and information-sharing behaviors.",
#         "Identify typical audience responses to praise, criticism, controversy, ideological conflict, and major external events.",
#         "Extract interaction rules between different audience segments, supporters, critics, and neutral observers.",
#         "Identify feedback loops that reinforce, weaken, or transform community beliefs over time.",
#         "Extract the variables, states, and transition rules required for an agent-based simulation of the ecosystem."
#     ]
# }

# # ============================================================
# # COMPACT GUIDELINES (Evidence & Mindset)
# # ============================================================

# detailed1_guidelines = [
#     "EVIDENCE FIRST: Collect sufficient evidence from diverse sources before attempting analysis. Rely on observations of audience behavior, not just the subject's claims.",
#     "EXTRACT, DO NOT DESCRIBE: Prioritize structured knowledge extraction (patterns, mechanisms, rules) over chronological narrative or descriptive text.",
#     "CAUSAL FOCUS: Explain the relationship between the subject's ideas, audience composition, communication style, and observed influence.",
# ]

# detailed2_guidelines = [
#     "Do not write a conventional biography.",
#     "The primary objective is to build a Digital Twin of the subject and the audience ecosystem surrounding them.",
#     "Treat the subject as an influence source and the audience as the primary system being modeled.",
#     "Prioritize structured knowledge extraction over narrative writing.",
#     "Identify recurring behavioral, ideological, cultural, communicative, and social patterns rather than isolated events.",
#     "Extract reusable knowledge suitable for behavioral simulation rather than descriptive summaries.",
#     "Reverse engineer the subject's worldview, ideology, epistemology, philosophy, methodology, and system of thought.",
#     "Identify the beliefs, values, assumptions, priorities, and recurring principles that consistently shape the subject's discourse.",
#     "Determine which ideas define the subject's public identity and which themes dominate their communication.",
#     "Analyze how the subject justifies truth, authority, evidence, morality, religion, politics, society, identity, and social order.",
#     "Carefully analyze ideological characteristics supported by evidence, including conservatism, liberalism, progressivism, nationalism, populism, sectarianism, exclusivism, traditionalism, reformism, political mobilization, religious fundamentalism, extremism, discrimination, conspiracy narratives, or similar recurring patterns whenever applicable.",
#     "Do not assign ideological labels unless supported by multiple independent pieces of evidence.",
#     "Carefully analyze the subject's positions regarding religion, politics, democracy, secularism, women, gender roles, minorities, human rights, violence, extremism, education, social norms, and other major societal issues whenever sufficient evidence exists.",
#     "Identify which ideas generate the strongest support, criticism, polarization, or controversy.",
#     "Treat the audience as a complex social system rather than a list of followers.",
#     "Identify audience demographics, ideological tendencies, education, geography, religiosity, socioeconomic characteristics, motivations, and cultural background whenever evidence exists.",
#     "Reverse engineer why different audience groups trust, reject, defend, or criticize the subject.",
#     "Analyze audience values, identities, fears, aspirations, moral intuitions, and cultural assumptions whenever observable evidence exists.",
#     "Analyze how different audience segments react to specific ideas rather than only measuring engagement.",
#     "Identify which ideas resonate most strongly with which communities and explain why.",
#     "Analyze disagreement inside the audience whenever multiple communities interpret the subject differently.",
#     "Analyze how ideas spread through books, lectures, institutions, YouTube, television, social media, personal networks, communities, organizations, and other dissemination mechanisms.",
#     "Explain the interaction between ideology, communication style, audience composition, dissemination channels, and observable influence rather than describing each independently.",
#     "Analyze rhetorical style, framing strategies, narratives, symbolism, emotional appeals, authority construction, persuasive techniques, storytelling, and educational methods.",
#     "Identify recurring messaging patterns and communication strategies.",
#     "Map important allies, critics, competing schools of thought, rival influencers, institutions, organizations, media ecosystems, and communities interacting with the subject."
# ]

# detailed_guidelines = detailed1_guidelines + detailed2_guidelines

# # ============================================================
# # HELPER FUNCTIONS
# # ============================================================

# def add_layer(target, layer):
#     """
#     Helper function to cleanly append a research layer into the query structure.
#     """
#     target.append(f"\n### {layer['name']}")
#     if "objective" in layer and layer["objective"]:
#         target.append(f"Objective: {layer['objective'].strip()}")
    
#     if "extraction_tasks" in layer:
#         target.append("Extraction Tasks:")
#         target.extend(f"- {q}" for q in layer["extraction_tasks"])

# # ============================================================
# # MAIN FUNCTION
# # ============================================================

# async def run_research_experiment():
    
#     subject_name = "Sheikh Mostafa Al-Adawy"
#     website_url = "https://mostafaaladwy.com"
#     short_description = "An Egyptian Salafi Islamic scholar, hadith specialist, and contemporary religious influencer."

#     # 1. Compact User Details
#     user_details = f"""
# Subject: {subject_name}

# {short_description}

# A prominent public figure with a substantial online presence whose ideas are disseminated through books, lectures, interviews, websites, YouTube, and other digital platforms.

# Official website:
# {website_url}
# """

#     # 2. Master Directives & Research Goal
#     master_directives = [
#         "Research Target: Ecosystem Reverse Engineering",
#         "",
#         "The subject is the observation target, not the final product.",
#         "",
#         "Reverse engineer the complete ecosystem surrounding the subject, including ideology, communication, audience formation, community dynamics, influence mechanisms, diffusion pathways, and behavioral patterns.",
#         "",
#         "Produce structured knowledge suitable for building computational Digital Twin and agent-based simulation models.",
#         "",
#         "Prioritize mechanisms over descriptions, causal relationships over isolated facts, and reusable behavioral models over narrative summaries.",
#         "",
#         "Subject Overview:",
#         user_details.strip(),
#         ""
#     ]

#     query_parts = list(master_directives)

#     # 3. Injecting the 8 Focused Layers in your specific requested order
#     add_layer(query_parts, identity_worldview_layer)
#     add_layer(query_parts, ideas_ideology_layer)
#     add_layer(query_parts, epistemology_layer)
#     add_layer(query_parts, narrative_communication_layer)
#     add_layer(query_parts, audience_community_layer)
#     add_layer(query_parts, influence_diffusion_layer)
#     add_layer(query_parts, mechanistic_layer)
#     add_layer(query_parts, simulation_layer)

#     full_detailed_query = "\n".join(query_parts)
    
#     state: GraphState = {
#         "user_initial_query": full_detailed_query, 
#         "chain_input": {
#             "query": full_detailed_query,
#             "guidelines": detailed_guidelines,
#             "follow_guidelines": True,
#             "max_sections": 8, # Modified to 8 to match the number of your layers
#             "verbose": True,
#         },
#         "profile_candidates": [],
#         "research_iteration": 0,
#     }

#     print("⏳ Running streamlined multi-agent intelligence profiling, please wait...")
#     result = await make_research(state)

#     candidate = result["profile_candidates"][0]

#     print("\nREPORT LENGTH:", len(candidate["full_report"]))
#     print("SOURCES:", len(candidate["sources"]))
#     print("COSTS:", candidate["costs"])

#     with open("multi_agent_test_report.md", "w", encoding="utf-8") as f:
#         f.write(candidate["full_report"])

#     print("\n✅ Saved: multi_agent_test_report.md")


# if __name__ == "__main__":
#     asyncio.run(run_research_experiment())