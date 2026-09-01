import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // This UI lives in a repo that also contains unrelated lockfiles; pin the
  // Turbopack workspace root to this directory.
  turbopack: {
    root: __dirname,
  },
  // Increase the proxy timeout for slow backend requests (e.g. proxy self-test
  // which goes through an external residential proxy).
  experimental: {
    proxyTimeout: 120_000,
  },
  // Next 16 dev serves scripts/module chunks with the crossorigin attribute,
  // so their requests carry an Origin header. Requests whose Origin is not in
  // this allowlist get 403 (hydration silently never runs). Allow the IPv4
  // loopback alias 127.0.0.1 in addition to localhost so e2e runs and direct
  // 127.0.0.1 browsing can hydrate. Production builds are unaffected.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Proxy the SocialScienceResearch FastAPI backend during development and
  // deployment so the browser never needs to talk cross-origin.
  // Start the backend with: uvicorn SocialScienceResearch.api:create_app --factory
  async rewrites() {
    // Single backend now serves both the social-science API and the research
    // agent API (CopilotKit runtime + /api/agent/*). Default to the same host as
    // the social-science backend (8000); override with AGENT_BACKEND_URL if split.
    const agentBackend = process.env.AGENT_BACKEND_URL ?? process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/social-science/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/v1/social-science/:path*`,
      },
      // Research agent server (CopilotKit runtime + log stream + direct run).
      {
        source: "/copilotkit/:path*",
        destination: `${agentBackend}/copilotkit/:path*`,
      },
      {
        source: "/api/agent/:path*",
        destination: `${agentBackend}/api/agent/:path*`,
      },
    ];
  },
};

export default nextConfig;
