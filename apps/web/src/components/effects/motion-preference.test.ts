import { prefersReducedMotion } from "./motion-preference";

afterEach(() => vi.unstubAllGlobals());

test("honours the browser preference and fails safe without matchMedia", () => {
  expect(prefersReducedMotion()).toBe(true);
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: false })),
  );
  expect(prefersReducedMotion()).toBe(false);
});
