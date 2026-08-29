"use client";

import { useState } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import { ChatPanel } from "./components/ChatPanel";
import { ContextRail } from "./components/ContextRail";
import { LogsDrawer } from "./components/LogsDrawer";
import { ActivityPill } from "./components/ActivityPill";
import { useAgentLogs } from "./hooks/useAgentLogs";

export function AgentWorkspace() {
  return (
    <CopilotKit runtimeUrl="/copilotkit" agent="research_agent">
      <AgentWorkspaceInner />
    </CopilotKit>
  );
}

function AgentWorkspaceInner() {
  const [logsOpen, setLogsOpen] = useState(false);
  const { events, counts, currentStage } = useAgentLogs();

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground text-[11px]">
            AI
          </span>
          Research Agent
        </div>
        <ActivityPill counts={counts} onClick={() => setLogsOpen((v) => !v)} />
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="min-h-0 flex-1">
          <ChatPanel />
        </div>
        <ContextRail
          events={events}
          counts={counts}
          currentStage={currentStage}
          onShowLogs={() => setLogsOpen(true)}
        />
      </div>

      <LogsDrawer
        open={logsOpen}
        onClose={() => setLogsOpen(false)}
        events={events}
      />
    </div>
  );
}
