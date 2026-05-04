import { create } from "zustand";

export type SetupStatus = "unknown" | "incomplete" | "complete";

interface SetupState {
  status: SetupStatus;
  setStatus: (status: SetupStatus) => void;
}

export const useSetupStore = create<SetupState>((set) => ({
  status: "unknown",
  setStatus: (status) => set({ status }),
}));
