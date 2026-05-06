// Wrappers around /api/folder/*.

export interface FolderScanItem {
  path: string;
  media_type: "photo" | "video";
  file_size: number;
}

export interface FolderScanResponse {
  folder: string;
  items: FolderScanItem[];
  photo_count: number;
  video_count: number;
  total_bytes: number;
  truncated: boolean;
}

export async function scanFolder(path: string): Promise<FolderScanResponse> {
  const r = await fetch(
    `/api/folder/scan?path=${encodeURIComponent(path)}`
  );
  if (!r.ok) {
    const detail = await safeDetail(r);
    throw new Error(detail || `Folder scan failed: ${r.status}`);
  }
  return (await r.json()) as FolderScanResponse;
}

async function safeDetail(r: Response): Promise<string> {
  try {
    const body = (await r.json()) as { detail?: string };
    return body.detail ?? "";
  } catch {
    return "";
  }
}
