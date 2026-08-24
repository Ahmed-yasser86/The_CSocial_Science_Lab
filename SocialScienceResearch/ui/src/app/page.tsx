import { WorkspaceChooser } from "@/components/features/workspace-chooser";

export default function Home() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Workspaces</h1>
        <p className="text-sm text-muted-foreground">
          Enter an existing workspace or create a new one. Collection tools
          live inside a workspace — pick one to continue.
        </p>
      </header>
      <WorkspaceChooser />
    </div>
  );
}
