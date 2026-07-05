import { ApiError } from "./client";
import { listTickets } from "./tickets";

afterEach(() => {
  vi.restoreAllMocks();
});

test("throws parsed API errors from ticket endpoints", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () =>
        Promise.resolve({
          error: { code: "forbidden", message: "Access denied." },
        }),
    }),
  );

  await expect(listTickets()).rejects.toEqual(new ApiError(403, "forbidden", "Access denied."));
});
