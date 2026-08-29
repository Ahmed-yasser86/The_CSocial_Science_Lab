"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { resolveChartColors } from "@/lib/colors";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

const STAGES = [
  { id: "identity_research", label: "Identity" },
  { id: "profile_summarization", label: "Profile" },
  { id: "subject_intelligence", label: "Subject" },
  { id: "audience_intelligence", label: "Audience" },
  { id: "ecosystem_intelligence", label: "Ecosystem" },
];

const LINKS = [
  { source: "identity_research", target: "profile_summarization" },
  { source: "profile_summarization", target: "subject_intelligence" },
  { source: "subject_intelligence", target: "audience_intelligence" },
  { source: "audience_intelligence", target: "ecosystem_intelligence" },
];

interface FGNode {
  id: string;
  label: string;
  x?: number;
  y?: number;
}

export function IntelligenceGraphView({ activeStage }: { activeStage?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 320, h: 240 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({
        w: Math.max(200, Math.floor(r.width)),
        h: Math.max(160, Math.floor(r.height)),
      });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const colors = useMemo(() => resolveChartColors(), []);
  const data = useMemo(
    () => ({
      nodes: STAGES.map((s) => ({ id: s.id, label: s.label })),
      links: LINKS.map((l) => ({ ...l })),
    }),
    [],
  );

  return (
    <div ref={ref} className="h-60 w-full">
      <ForceGraph2D
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeLabel={(n: any) => (n as FGNode)?.label ?? String(n?.id ?? "")}
        nodeColor={(n: any) =>
          (n as FGNode)?.id === activeStage ? colors.accent : colors.inkMuted
        }
        nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, scale: number) => {
          const node = n as FGNode;
          const r = 6;
          ctx.beginPath();
          ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
          ctx.fillStyle =
            node.id === activeStage ? colors.accent : colors.inkMuted;
          ctx.fill();
          ctx.font = `${12 / scale}px sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillStyle = colors.ink;
          ctx.fillText(node.label, node.x ?? 0, (node.y ?? 0) + r + 2);
        }}
        linkColor={() => colors.faint}
        cooldownTicks={100}
      />
    </div>
  );
}
