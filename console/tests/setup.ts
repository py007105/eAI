import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { server } from "./server";
let nativeFetch: typeof fetch;
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  nativeFetch = globalThis.fetch.bind(globalThis);
  vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) =>
    nativeFetch(new URL(String(input), window.location.href), {
      ...init,
      signal: undefined,
    }),
  );
  vi.stubGlobal("scrollTo", vi.fn());
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
