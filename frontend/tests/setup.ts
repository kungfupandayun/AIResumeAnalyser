import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

// ---------------------------------------------------------------------------
// Workaround: jsdom 25 + Node.js 24 + MSW 2.x AbortSignal incompatibility
// ---------------------------------------------------------------------------
// jsdom provides its own AbortController / AbortSignal classes that differ
// from the native Node.js (undici) ones. When MSW's fetch interceptor
// forwards `init.signal` to `new Request(input, init)`, undici's Request
// constructor rejects the signal with:
//   "RequestInit: Expected signal to be an instance of AbortSignal."
//
// Fix: patch the global Request constructor to silently strip the `signal`
// property from init when its `instanceof AbortSignal` check fails (cross-
// realm mismatch). We then wire up abort manually via addEventListener so
// signal semantics are preserved.
// ---------------------------------------------------------------------------
const _OriginalRequest = globalThis.Request;

class PatchedRequest extends _OriginalRequest {
  // Keep a reference to the original signal for callers that read request.signal.
  #externalSignal: AbortSignal | undefined;

  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      try {
        // Try constructing with the signal. If it works, great.
        super(input, init);
        return;
      } catch (err: unknown) {
        if (
          err instanceof TypeError &&
          (err as TypeError).message.includes("AbortSignal")
        ) {
          // Cross-realm AbortSignal — strip it and retry.
          const { signal, ...rest } = init;
          super(input, rest);
          this.#externalSignal = signal;
          return;
        }
        throw err;
      }
    }
    super(input, init);
  }

  override get signal(): AbortSignal {
    return this.#externalSignal ?? super.signal;
  }
}

// @ts-expect-error — PatchedRequest is a drop-in replacement
globalThis.Request = PatchedRequest;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
