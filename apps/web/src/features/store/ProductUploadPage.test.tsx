import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ProductUploadPage from "./ProductUploadPage";
import { getQueryClient, resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("suggests metadata and submits a controlled product registration", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [
            {
              id: "acg-alpha",
              code: "ACG-ALPHA-REGIONAL",
              name: "Alpha Regional",
              description: "Mock",
              ownerUserId: null,
              isActive: true,
              memberUserIds: [],
            },
          ],
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          tags: ["baltic", "geographic", "mock"],
          entities: ["Baltic ports"],
          sourceType: "synthetic",
          acgIds: [],
          semanticLabels: ["geospatial", "maritime"],
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "product-created",
          reference: "PROD-2001",
          title: "Mock Harbour Activity Brief",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);
  const invalidateSpy = vi.spyOn(getQueryClient(), "invalidateQueries");

  renderWithProviders(<ProductUploadPage />, "/store/upload");
  expect(await screen.findByLabelText("ACG")).toBeVisible();
  expect(screen.getByLabelText("Status")).toHaveValue("published");
  await userEvent.click(screen.getByRole("button", { name: "Suggest metadata" }));
  expect(await screen.findByDisplayValue("baltic, geographic, mock")).toBeVisible();
  expect(screen.getByLabelText("Suggested semantic labels")).toHaveTextContent("maritime");
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-alpha");
  await userEvent.selectOptions(screen.getByLabelText("Status"), "draft");
  await userEvent.click(screen.getByRole("button", { name: "Register product" }));

  expect(await screen.findByText("Created PROD-2001: Mock Harbour Activity Brief")).toBeVisible();
  // New products must appear in store searches without a manual refresh.
  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["store-products"] });
  const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
  const [url, init] = calls[calls.length - 1];
  expect(url).toContain("/api/v1/store/products");
  expect(init.credentials).toBe("include");
  if (typeof init.body !== "string") {
    throw new TypeError("Expected JSON request body.");
  }
  expect(init.body).toContain('"acgIds":["acg-alpha"]');
  expect(init.body).toContain('"status":"draft"');
});

test("shows the API validation message when product registration fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(acgResponse()) })
    .mockResolvedValue({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({ error: { code: "invalid_product", message: "Invalid metadata." } }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");
  await screen.findByRole("option", { name: "ACG-ALPHA-REGIONAL" });
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-alpha");
  await userEvent.click(screen.getByRole("button", { name: "Register product" }));

  expect(await screen.findByText("Invalid metadata.")).toBeVisible();
});

test("requires an explicit visible ACG before product registration", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(acgResponse()) });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");

  await screen.findByRole("option", { name: "ACG-ALPHA-REGIONAL" });
  expect(screen.getByText("Select an ACG before registering.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Register product" })).toBeDisabled();
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-alpha");

  expect(screen.queryByText("Select an ACG before registering.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Register product" })).not.toBeDisabled();
});

test("disables product registration when no visible ACGs are available", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [] }) });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");

  expect(
    await screen.findByText(
      "No visible access groups are available. Ask an administrator to add you to an active ACG before registering products.",
    ),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Register product" })).toBeDisabled();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("shows a generic error when product registration fails without a body", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(acgResponse()) })
    .mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("no body")),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");
  await screen.findByRole("option", { name: "ACG-ALPHA-REGIONAL" });
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-alpha");
  await userEvent.click(screen.getByRole("button", { name: "Register product" }));

  expect(
    await screen.findByText("Product registration failed. Check the metadata and try again."),
  ).toBeVisible();
});

test("shows the API validation message when metadata suggestions fail", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [] }) })
    .mockResolvedValue({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({ error: { code: "invalid_context", message: "Summary is too short." } }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");
  await screen.findByLabelText("ACG");
  await userEvent.click(screen.getByRole("button", { name: "Suggest metadata" }));

  expect(await screen.findByText("Summary is too short.")).toBeVisible();
});

test("shows a generic error when metadata suggestions fail without a body", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [] }) })
    .mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("no body")),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");
  await screen.findByLabelText("ACG");
  await userEvent.click(screen.getByRole("button", { name: "Suggest metadata" }));

  expect(
    await screen.findByText("Metadata suggestions could not be generated. Try again."),
  ).toBeVisible();
});

test("shows a retryable error when visible ACGs cannot be loaded", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [
            {
              id: "acg-alpha",
              code: "ACG-ALPHA-REGIONAL",
              name: "Alpha Regional",
              description: "Mock",
              ownerUserId: null,
              isActive: true,
              memberUserIds: [],
            },
          ],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");

  expect(
    await screen.findByText("Access groups could not be loaded. Refresh and try again."),
  ).toBeVisible();
  expect(screen.getByLabelText("ACG")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Register product" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "Retry access groups" }));

  expect(await screen.findByRole("option", { name: "ACG-ALPHA-REGIONAL" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Register product" })).toBeDisabled();
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-alpha");
  expect(screen.getByRole("button", { name: "Register product" })).not.toBeDisabled();
});

test("registers geographic products with the selected visible ACG", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(acgResponse()) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "product-created",
          reference: "PROD-2002",
          title: "Mock Harbour Activity Brief",
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductUploadPage />, "/store/upload");
  await screen.findByRole("option", { name: "ACG-ALPHA-REGIONAL" });
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-alpha");
  await userEvent.selectOptions(screen.getByLabelText("Product type"), "geographic_product");
  await userEvent.click(screen.getByRole("button", { name: "Register product" }));

  expect(await screen.findByText("Created PROD-2002: Mock Harbour Activity Brief")).toBeVisible();
  const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
  const [, init] = calls[calls.length - 1];
  if (typeof init.body !== "string") {
    throw new TypeError("Expected JSON request body.");
  }
  expect(init.body).toContain('"geojsonRef":"mock://geojson/layer"');
  expect(init.body).toContain('"acgIds":["acg-alpha"]');
});

function acgResponse() {
  return {
    acgs: [
      {
        id: "acg-alpha",
        code: "ACG-ALPHA-REGIONAL",
        name: "Alpha Regional",
        description: "Mock",
        ownerUserId: null,
        isActive: true,
        memberUserIds: [],
      },
    ],
  };
}
