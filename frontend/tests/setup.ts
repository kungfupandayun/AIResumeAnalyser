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
// Fix: subclass the global Request. Strip a cross-realm signal from init
// before calling super(), preserve it in a WeakMap, and re-expose it via a
// signal getter override. A WeakMap (instead of a private class field) keeps
// super() the root statement of the constructor so TS doesn't reject it.
// ---------------------------------------------------------------------------
const _OriginalRequest = globalThis.Request;

const signalMap = new WeakMap<Request, AbortSignal>();

function stripCrossRealmSignal(
  input: RequestInfo | URL,
  init: RequestInit,
): { init: RequestInit; externalSignal: AbortSignal | undefined } {
  if (!init.signal) return { init, externalSignal: undefined };
  try {
    // Probe whether undici accepts this signal. If it does, no strip needed.
    new _OriginalRequest(input, init);
    return { init, externalSignal: undefined };
  } catch (err: unknown) {
    if (
      err instanceof TypeError &&
      err.message.includes("AbortSignal")
    ) {
      const { signal, ...rest } = init;
      return { init: rest, externalSignal: signal };
    }
    throw err;
  }
}

class PatchedRequest extends _OriginalRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    const { init: actualInit, externalSignal } = stripCrossRealmSignal(input, init ?? {});
    super(input, actualInit);
    if (externalSignal) signalMap.set(this, externalSignal);
  }

  override get signal(): AbortSignal {
    return signalMap.get(this) ?? super.signal;
  }
}

globalThis.Request = PatchedRequest as typeof globalThis.Request;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
