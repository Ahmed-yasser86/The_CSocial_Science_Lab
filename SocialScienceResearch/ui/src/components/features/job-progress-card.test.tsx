import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import type { Job } from "@/lib/types";

vi.mock("@/services/queries", () => ({
  useJob: vi.fn(),
  useCancelJob: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));

import { JobProgressCard } from "@/components/features/job-progress-card";
import { useJob } from "@/services/queries";

const mockUseJob = vi.mocked(useJob);

function cast<T>(value: unknown): T {
  return value as T;
}

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    job_id: "job_1",
    kind: "layer",
    status: "running",
    created_at: "2026-08-25T00:00:00Z",
    started_at: "2026-08-25T00:00:01Z",
    finished_at: null,
    progress: {
      stage: "layer/enrich",
      discovered: 10,
      succeeded: 4,
      failed: 1,
      message: "Enriched 4/10 target video(s)",
    },
    message: "Enriched 4/10 target video(s)",
    cancel_requested: false,
    ...overrides,
  };
}

function mockQuery(job: Job | undefined) {
  return cast<ReturnType<typeof useJob>>({ data: job });
}

describe("JobProgressCard structured progress (layer crawl)", () => {
  beforeEach(() => {
    mockUseJob.mockReset();
  });

  it("renders server percent, counts, edges saved and ETA when known", () => {
    mockUseJob.mockReturnValue(
      mockQuery(
        makeJob({
          progress: {
            stage: "layer/enrich",
            discovered: 10,
            succeeded: 4,
            failed: 1,
            message: null,
            percent_complete: 50,
            eta_seconds: 120,
            eta_available: true,
            edges_saved: 400,
            current_target: { video_id: "t5", title: "Target Five", url: null },
            failures: [
              { video_id: "t2", error: "Unsupported" },
              { video_id: "t4", error: "Timeout" },
            ],
          },
        }),
      ),
    );
    renderWithProviders(<JobProgressCard jobId="job_1" />);

    expect(screen.getByText(/4 succeeded, 1 failed/)).toBeInTheDocument();
    expect(screen.getByText(/10 discovered/)).toBeInTheDocument();
    expect(screen.getByText(/400 edge\(s\) saved/)).toBeInTheDocument();
    expect(screen.getByText("~2m remaining")).toBeInTheDocument();
    expect(screen.getByText(/Now:/)).toBeInTheDocument();
    expect(screen.getByText("Target Five")).toBeInTheDocument();
    // Failures start collapsed behind an expandable summary.
    expect(screen.getByText(/2 failed items/)).toBeInTheDocument();
  });

  it("hides the ETA when no honest estimate exists", () => {
    mockUseJob.mockReturnValue(
      mockQuery(
        makeJob({
          progress: {
            stage: "layer/scrape",
            discovered: 0,
            succeeded: 0,
            failed: 0,
            message: null,
            percent_complete: null,
            eta_seconds: null,
            eta_available: false,
          },
        }),
      ),
    );
    renderWithProviders(<JobProgressCard jobId="job_1" />);
    expect(screen.queryByText(/remaining/)).not.toBeInTheDocument();
  });

  it("renders per-item failures inside an expandable details block", () => {
    mockUseJob.mockReturnValue(
      mockQuery(
        makeJob({
          progress: {
            stage: "layer/enrich",
            discovered: 3,
            succeeded: 1,
            failed: 2,
            message: null,
            failures: [
              { video_id: "vid_aaa", error: "no support" },
              { video_id: "vid_bbb", error: "boom" },
            ],
          },
        }),
      ),
    );
    renderWithProviders(<JobProgressCard jobId="job_1" />);

    // jsdom does not toggle <details> on summary clicks, so assert the
    // collapsed-by-default structure and its hidden content instead.
    const summary = screen.getByText(/2 failed items/);
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(details).toHaveTextContent("vid_aaa");
    expect(details).toHaveTextContent("no support");
    expect(details).toHaveTextContent("vid_bbb");
  });

  it("falls back to locally computed percent when the server omits it", () => {
    mockUseJob.mockReturnValue(mockQuery(makeJob()));
    renderWithProviders(<JobProgressCard jobId="job_1" />);
    // 5 of 10 done -> 50%
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "50");
  });
});
