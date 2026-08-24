import Link from "next/link";
import { BookOpen } from "lucide-react";

const SECTION = "scroll-mt-20";

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className={`${SECTION} mt-10 border-b pb-1.5 text-lg font-semibold tracking-tight`}>
      {children}
    </h2>
  );
}

function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>;
}

function P({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <p className={`mt-3 text-sm leading-relaxed text-foreground/90 ${className}`}>{children}</p>;
}

function UL({ children }: { children: React.ReactNode }) {
  return <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-foreground/90">{children}</ul>;
}

export const metadata = {
  title: "Docs",
  description: "What each feature of the Social Science Research Workbench does.",
};

export default function DocsPage() {
  return (
    <article className="mx-auto max-w-3xl">
      <header className="flex items-center gap-2">
        <BookOpen className="size-5 text-primary" aria-hidden />
        <h1 className="text-2xl font-semibold tracking-tight">Documentation</h1>
      </header>
      <p className="mt-2 text-sm text-muted-foreground">
        A guide to what each part of the workbench does and how the pieces fit together.
        The platform observes YouTube data reproducibly — values are recorded as observed, never
        estimated, and missing data is reported explicitly.
      </p>

      <nav aria-label="On this page" className="mt-6 rounded-md border bg-muted/40 p-3 text-sm">
        <p className="font-medium">On this page</p>
        <ul className="mt-1.5 grid gap-1 sm:grid-cols-2">
          <li><Link className="underline-offset-2 hover:underline" href="#collect">Collect</Link></li>
          <li><Link className="underline-offset-2 hover:underline" href="#scrape-recommendations">Scrape recommendations</Link></li>
          <li><Link className="underline-offset-2 hover:underline" href="#crawl-next-layer">Crawl next layer</Link></li>
          <li><Link className="underline-offset-2 hover:underline" href="#network">Network (ego view)</Link></li>
          <li><Link className="underline-offset-2 hover:underline" href="#lab">Lab (full network)</Link></li>
          <li><Link className="underline-offset-2 hover:underline" href="#compare">Compare</Link></li>
          <li><Link className="underline-offset-2 hover:underline" href="#export">Export formats</Link></li>
          <li><Link className="underline-offset-2 hover:underline" href="#provenance">Provenance &amp; data</Link></li>
        </ul>
      </nav>

      <H2 id="collect">Collect</H2>
      <P>
        The <Link className="underline-offset-2 hover:underline" href="/collect">Collect</Link> page triggers a
        collection run. You can collect a <strong>channel</strong> (its videos + metadata), a single{" "}
        <strong>video</strong> (its metadata/engagement), or a <strong>recommendation observation</strong> for a
        video (its &ldquo;Up Next&rdquo; rail). Every collection is recorded as a{" "}
        <Link className="underline-offset-2 hover:underline" href="/runs">Run</Link> for full provenance, and a
        bulk recommendation scrape registers one sub-run per source video.
      </P>

      <H2 id="scrape-recommendations">Scrape recommendations</H2>
      <P>
        &ldquo;Scrape recommendations&rdquo; observes the directed recommendation edges leaving a video — i.e. the
        videos YouTube surfaces as &ldquo;Up Next&rdquo; / &ldquo;recommended&rdquo; after it. Each observed
        recommendation is stored as a directed edge{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">source_video_id &rarr; recommended_video_id</code>{" "}
        with its feed <em>position</em> (rank) and the <em>run</em> that observed it.
      </P>
      <H3>How extraction works</H3>
      <UL>
        <li>
          A <strong>layered provider strategy</strong> is used: the yt-dlp library fields, the INNERTUBE{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">/next</code> endpoint, and watch-page dumps. If
          every provider returns nothing, the system records an explicit <em>unsupported</em> error rather than
          fabricating edges.
        </li>
        <li>
          Each newly seen recommended target video is then <strong>deep-enriched</strong> (its own metadata, and
          comments when enabled) so it can later become a central node in the network.
        </li>
        <li>
          Deep-enrichment is <strong>bounded</strong> by <code className="rounded bg-muted px-1 py-0.5 text-xs">max_enrich_targets</code>{" "}
          (default 100, tunable in <Link className="underline-offset-2 hover:underline" href="/collect">Collect</Link>{" "}
          speed settings, <code className="rounded bg-muted px-1 py-0.5 text-xs">0</code> = unlimited). Edges are
          saved for <em>every</em> recommendation regardless; only the slower per-video enrichment is capped, which
          guarantees a scrape always completes.
        </li>
      </UL>
      <P>
        This action appears in several places: a single video&rsquo;s <strong>Network</strong> tab (&ldquo;Scrape
        recommendations&rdquo;), an ego/full network&rsquo;s &ldquo;Scrape all recommendations&rdquo; (expands the
        whole visible slice one hop), and the <Link className="underline-offset-2 hover:underline" href="/network/full">Lab</Link>{" "}
        expansion panel.
      </P>

      <H2 id="crawl-next-layer">Crawl next layer (create next layer)</H2>
      <P>
        Recommendation networks are grown <strong>layer by layer</strong> (a breadth-first crawl). This is the
        &ldquo;Crawl next layer&rdquo; action in the{" "}
        <Link className="underline-offset-2 hover:underline" href="/network/full">Lab</Link>&rsquo;s layer stepper.
      </P>
      <H3>Seed layer &rarr; subsequent layers</H3>
      <UL>
        <li>
          <strong>Bootstrap a seed layer (Layer 0)</strong> from an existing run or channel&rsquo;s videos. This is
          the starting frontier.
        </li>
        <li>
          <strong>Crawl next layer</strong> takes the current frontier and scrapes each frontier
          video&rsquo;s recommendations one hop outward, producing a new <code className="rounded bg-muted px-1 py-0.5 text-xs">LayerRun</code>{" "}
          (Layer 1, Layer 2, &hellip;). New target videos are deep-enriched and all edges are persisted, so the
          graph keeps growing.
        </li>
        <li>
          Because deep-enrichment is bounded by <code className="rounded bg-muted px-1 py-0.5 text-xs">max_enrich_targets</code>,{" "}
          a layer crawl always <strong>completes and forms the next layer</strong> instead of appearing to hang on a
          slow extraction.
        </li>
      </UL>
      <P>
        Each layer carries a <strong>relation report</strong>: the new edges, new videos, and new connected
        components it contributes relative to all <em>earlier</em> layers. This makes the layer-comparison matrix
        (see <Link className="underline-offset-2 hover:underline" href="#compare">Compare</Link>) stable regardless
        of crawl order — each layer&rsquo;s deltas are measured against a corpus that excludes later layers.
      </P>

      <H2 id="network">Network (ego view)</H2>
      <P>
        A video&rsquo;s <strong>Network</strong> tab shows its <em>connected recommendation web</em>: who recommends
        it (in-edges), whom it recommends (out-edges), and the cross-links among them. You can filter by run,
        channel, node role (source / target / both / other), minimum degree, and title presence.
      </P>
      <P>
        Use <strong>Export</strong> (in the Graph card header) to download the currently visible graph in several
        formats — see <Link className="underline-offset-2 hover:underline" href="#export">Export formats</Link>.
      </P>

      <H2 id="lab">Lab (full network)</H2>
      <P>
        The <Link className="underline-offset-2 hover:underline" href="/network/full">Lab</Link> analyzes the{" "}
        <em>entire</em> observed recommendation graph for a research scope: communities, HITS authority/hub ranks,
        PageRank, and isolated-node detection. It also hosts the layer stepper (crawl next layer) and expansion
        (scrape recommendations) actions.
      </P>

      <H2 id="compare">Compare</H2>
      <P>
        <Link className="underline-offset-2 hover:underline" href="/compare">Compare</Link> renders the
        layer-comparison matrix: for each layer, how many edges / videos / components it added. Deltas are computed
        against earlier layers only, so the matrix is consistent no matter which layers were crawled first.
      </P>

      <H2 id="export">Export formats</H2>
      <P>
        The Network (ego) view&rsquo;s <strong>Export</strong> menu downloads the currently filtered graph (what you
        see on screen). Available formats:
      </P>
      <UL>
        <li><strong>Edge list (CSV)</strong> — one row per directed edge: <code className="rounded bg-muted px-1 py-0.5 text-xs">source_video_id, target_video_id, source_title, target_title, run_id, run_type, position</code>. Ready for network tools (Gephi, NetworkX, igraph).</li>
        <li><strong>Nodes (CSV)</strong> — one row per video node: <code className="rounded bg-muted px-1 py-0.5 text-xs">video_id, title, kind, in_degree, out_degree, channel_id</code>.</li>
        <li><strong>Graph (JSON)</strong> — the full <code className="rounded bg-muted px-1 py-0.5 text-xs">{"{ nodes, links }"}</code> object with an <code className="rounded bg-muted px-1 py-0.5 text-xs">exported_at</code> timestamp.</li>
        <li><strong>Spreadsheet (XLSX)</strong> — a real multi-sheet Excel workbook with an <code className="rounded bg-muted px-1 py-0.5 text-xs">Edges</code> sheet and a <code className="rounded bg-muted px-1 py-0.5 text-xs">Nodes</code> sheet.</li>
      </UL>

      <H2 id="provenance">Provenance &amp; data</H2>
      <UL>
        <li><Link className="underline-offset-2 hover:underline" href="/runs">Runs</Link> — the ledger of every collection; each run records what was scraped, when, and with which config.</li>
        <li><Link className="underline-offset-2 hover:underline" href="/datasets">Datasets</Link> &amp; <Link className="underline-offset-2 hover:underline" href="/projects">Projects</Link> — organize runs and exports into shareable research artifacts.</li>
        <li><Link className="underline-offset-2 hover:underline" href="/data">Data</Link>, <Link className="underline-offset-2 hover:underline" href="/samples">Samples</Link>, <Link className="underline-offset-2 hover:underline" href="/query">Query</Link>, <Link className="underline-offset-2 hover:underline" href="/explore">Explorer</Link> — browse, sample, and query the raw observed records (videos, comments, channels, recommendations, authors).</li>
      </UL>
      <P className="mt-8 rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
        Tip: filter the Network view first, then Export — the download reflects exactly the visible graph.
      </P>
    </article>
  );
}
