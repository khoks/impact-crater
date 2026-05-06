// Holds the form state for the multi-route new-project flow:
//   /projects/new        → name + brief + folder + audio + duration
//   /projects/new/effort → effort levels + cost preview + Submit
// Cleared after the job is submitted.

import { create } from "zustand";

export interface NewProjectDraft {
  name: string;
  brief: string;
  folder_path: string;
  audio_path: string;
  target_duration_seconds: number;
  // Folder-scan results live here so the effort-level page doesn't re-fetch.
  scanned_media_paths: string[];
  scanned_photo_count: number;
  scanned_video_count: number;
  scanned_total_bytes: number;
}

interface NewProjectState {
  draft: NewProjectDraft | null;
  setDraft: (draft: NewProjectDraft) => void;
  reset: () => void;
}

export const useNewProjectStore = create<NewProjectState>((set) => ({
  draft: null,
  setDraft: (draft) => set({ draft }),
  reset: () => set({ draft: null }),
}));
