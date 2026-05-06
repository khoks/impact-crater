import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import NewProject from "../routes/NewProject";
import { useNewProjectStore } from "../stores/newProjectStore";

interface MockResponse {
  ok: boolean;
  status: number;
  body: unknown;
}

function mockFetchSequence(responses: MockResponse[]): void {
  let i = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const r = responses[i++];
      if (!r) throw new Error(`No mock for fetch ${url}`);
      return {
        ok: r.ok,
        status: r.status,
        json: async () => r.body,
      };
    }) as unknown as typeof fetch
  );
}

beforeEach(() => {
  useNewProjectStore.setState({ draft: null });
  vi.unstubAllGlobals();
});

describe("NewProject", () => {
  it("disables Continue until name + brief + scan + audio are all set", async () => {
    render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <Routes>
          <Route path="/projects/new" element={<NewProject />} />
        </Routes>
      </MemoryRouter>
    );
    const continueButton = screen.getByRole("button", { name: /continue/i });
    expect(continueButton).toBeDisabled();
  });

  it("scans the folder and surfaces photo + video counts", async () => {
    mockFetchSequence([
      {
        ok: true,
        status: 200,
        body: {
          folder: "/tmp/photos",
          items: [
            { path: "/tmp/photos/a.jpg", media_type: "photo", file_size: 1234 },
            { path: "/tmp/photos/b.jpg", media_type: "photo", file_size: 1234 },
            { path: "/tmp/photos/c.mp4", media_type: "video", file_size: 9999 },
          ],
          photo_count: 2,
          video_count: 1,
          total_bytes: 12467,
          truncated: false,
        },
      },
    ]);

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <Routes>
          <Route path="/projects/new" element={<NewProject />} />
        </Routes>
      </MemoryRouter>
    );

    const folderInput = screen.getByPlaceholderText(/Pictures.Alps2026/);
    await user.type(folderInput, "/tmp/photos");
    await user.click(screen.getByRole("button", { name: /^Scan$/i }));
    await waitFor(() => {
      // Text spans multiple <strong> elements; pick the leaf-most match so we
      // don't grab every parent up to <body>.
      const node = screen.getByText((_, el) => {
        if (!el) return false;
        const text = (el.textContent ?? "").trim();
        if (!text.includes("2 photos + 1 video")) return false;
        const childTexts = Array.from(el.children).map(
          (c) => c.textContent ?? ""
        );
        return !childTexts.some((c) => c.includes("2 photos + 1 video"));
      });
      expect(node).toBeInTheDocument();
    });
  });

  it("shows the scan error when the folder request fails", async () => {
    mockFetchSequence([
      { ok: false, status: 400, body: { detail: "path does not exist: /nope" } },
    ]);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <Routes>
          <Route path="/projects/new" element={<NewProject />} />
        </Routes>
      </MemoryRouter>
    );
    await user.type(screen.getByPlaceholderText(/Pictures.Alps2026/), "/nope");
    await user.click(screen.getByRole("button", { name: /^Scan$/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/path does not exist/);
    });
  });

  it("enables Continue and stashes the draft when all fields are populated", async () => {
    mockFetchSequence([
      {
        ok: true,
        status: 200,
        body: {
          folder: "/tmp/photos",
          items: [
            { path: "/tmp/photos/a.jpg", media_type: "photo", file_size: 1234 },
          ],
          photo_count: 1,
          video_count: 0,
          total_bytes: 1234,
          truncated: false,
        },
      },
    ]);

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <Routes>
          <Route path="/projects/new" element={<NewProject />} />
          <Route
            path="/projects/new/effort"
            element={<div>EFFORT_ROUTE</div>}
          />
        </Routes>
      </MemoryRouter>
    );

    await user.type(screen.getByPlaceholderText(/Alps trip/), "Alps");
    await user.type(
      screen.getByPlaceholderText(/Highlight reel/),
      "warm to cool"
    );
    await user.type(
      screen.getByPlaceholderText(/Pictures.Alps2026/),
      "/tmp/photos"
    );
    await user.click(screen.getByRole("button", { name: /^Scan$/i }));
    await waitFor(() => {
      const node = screen.getByText((_, el) => {
        if (!el) return false;
        const text = (el.textContent ?? "").trim();
        if (!text.includes("1 photo + 0 videos")) return false;
        const childTexts = Array.from(el.children).map(
          (c) => c.textContent ?? ""
        );
        return !childTexts.some((c) => c.includes("1 photo + 0 videos"));
      });
      expect(node).toBeInTheDocument();
    });

    await user.type(
      screen.getByPlaceholderText(/track\.mp3/),
      "/tmp/song.mp3"
    );
    const continueButton = screen.getByRole("button", { name: /continue/i });
    expect(continueButton).not.toBeDisabled();
    await user.click(continueButton);

    await waitFor(() => {
      expect(screen.getByText("EFFORT_ROUTE")).toBeInTheDocument();
    });
    expect(useNewProjectStore.getState().draft).toMatchObject({
      name: "Alps",
      brief: "warm to cool",
      audio_path: "/tmp/song.mp3",
      scanned_photo_count: 1,
      mode: "standard",
    });
  });

  it("reveals the section-to-media textarea when music_video is selected", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <Routes>
          <Route path="/projects/new" element={<NewProject />} />
        </Routes>
      </MemoryRouter>
    );
    // Default = standard, textarea hidden.
    expect(screen.queryByPlaceholderText(/Intro should be slow/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Music video/i }));
    expect(
      screen.getByPlaceholderText(/Intro should be slow/i)
    ).toBeInTheDocument();
    // Switching back hides it.
    await user.click(screen.getByRole("radio", { name: /Standard/i }));
    expect(screen.queryByPlaceholderText(/Intro should be slow/i)).not.toBeInTheDocument();
  });

  it("stashes mode + section_to_media_nl in the draft", async () => {
    mockFetchSequence([
      {
        ok: true,
        status: 200,
        body: {
          folder: "/tmp/photos",
          items: [
            { path: "/tmp/photos/a.jpg", media_type: "photo", file_size: 1234 },
          ],
          photo_count: 1,
          video_count: 0,
          total_bytes: 1234,
          truncated: false,
        },
      },
    ]);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/projects/new"]}>
        <Routes>
          <Route path="/projects/new" element={<NewProject />} />
          <Route path="/projects/new/effort" element={<div>EFFORT</div>} />
        </Routes>
      </MemoryRouter>
    );
    await user.type(screen.getByPlaceholderText(/Alps trip/), "Hike");
    await user.type(
      screen.getByPlaceholderText(/Highlight reel/),
      "summit attempt"
    );
    await user.type(
      screen.getByPlaceholderText(/Pictures.Alps2026/),
      "/tmp/photos"
    );
    await user.click(screen.getByRole("button", { name: /^Scan$/i }));
    await waitFor(() => {
      expect(screen.getByText(/MB/)).toBeInTheDocument();
    });
    await user.type(
      screen.getByPlaceholderText(/track\.mp3/),
      "/tmp/song.mp3"
    );
    await user.click(screen.getByRole("radio", { name: /Music video/i }));
    await user.type(
      screen.getByPlaceholderText(/Intro should be slow/i),
      "intro=warm; chorus=summit"
    );
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => {
      expect(screen.getByText("EFFORT")).toBeInTheDocument();
    });
    expect(useNewProjectStore.getState().draft).toMatchObject({
      mode: "music_video",
      section_to_media_nl: "intro=warm; chorus=summit",
    });
  });
});
