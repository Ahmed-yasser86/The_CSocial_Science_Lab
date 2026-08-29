import { ResearchConsole } from "@/agent-ui/ResearchConsole";

export const metadata = {
  title: "Research Agent",
};

export default function AgentPage() {
  return (
    <div className="-m-4 md:-m-6 h-[calc(100dvh-3.5rem)]">
      <ResearchConsole />
    </div>
  );
}
