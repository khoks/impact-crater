import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { TOKEN_META_NAME } from "./api/client";

// The served page carries the API token in this meta tag; give every test one so
// apiFetch never needs the /api/session fallback (covered in apiClient.test.ts).
const meta = document.createElement("meta");
meta.name = TOKEN_META_NAME;
meta.content = "test-token";
document.head.appendChild(meta);

afterEach(() => {
  cleanup();
});
