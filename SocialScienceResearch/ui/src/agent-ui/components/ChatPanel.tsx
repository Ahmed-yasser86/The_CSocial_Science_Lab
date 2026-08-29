"use client";

import { CopilotChat } from "@copilotkit/react-ui";

export function ChatPanel() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <CopilotChat
        instructions="You control the research_agent pipeline. When the user names a subject or asks for intelligence (subject, audience, or ecosystem), invoke the research_agent with a user_query (and input_paths if provided). Then summarize the produced reports for the user."
        labels={{
          title: "Research Agent",
          initial:
            "Describe a subject or ask for intelligence (subject / audience / ecosystem)…",
        }}
        className="h-full!"
      />
    </div>
  );
}
