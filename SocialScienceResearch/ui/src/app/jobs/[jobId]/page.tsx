import { JobDetailPage } from "@/components/features/job-detail-page";

export default async function JobDetailRoute({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  return <JobDetailPage jobId={jobId} />;
}
