const API_PREFIX = "/api/v1/social-science";
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function serverJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BACKEND_URL}${API_PREFIX}${path}`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export interface VideoMeta {
  title: string | null;
}

export interface ProjectMeta {
  name: string;
}

export async function getVideoMeta(videoId: string): Promise<string | null> {
  const video = await serverJson<VideoMeta>(`/videos/${videoId}`);
  return video?.title ?? null;
}

export async function getProjectMeta(projectId: string): Promise<string | null> {
  const project = await serverJson<ProjectMeta>(`/projects/${projectId}`);
  return project?.name ?? null;
}

export interface ProjectItemMeta {
  name: string;
}

export async function getProjectItemMeta(
  projectId: string,
  itemId: string,
): Promise<string | null> {
  const item = await serverJson<ProjectItemMeta>(
    `/projects/${projectId}/items/${itemId}`,
  );
  return item?.name ?? null;
}

export interface ChannelMeta {
  title: string | null;
}

export async function getChannelMeta(channelId: string): Promise<string | null> {
  const channel = await serverJson<ChannelMeta>(`/channels/${channelId}`);
  return channel?.title ?? null;
}
