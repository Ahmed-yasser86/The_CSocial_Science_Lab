import { AiConfig } from "@/agent-ui/AiConfig";

export const metadata = {
  title: "AI Configuration",
};

export default function AiConfigPage() {
  return (
    <div className="-m-4 md:-m-6 h-[calc(100dvh-3.5rem)] overflow-y-auto">
      <div className="mx-auto max-w-5xl p-5">
        <AiConfig />
      </div>
    </div>
  );
}
