import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AcgAdminPage from "./AcgAdminPage";
import { AppProviders } from "../../app/providers";
import { resetQueryClientForTests } from "../../app/query-client";
import { previewSession } from "../../test/test-utils";

const acg = {
  id: "acg-alpha",
  code: "ACG-ALPHA",
  name: "Alpha Regional",
  description: "Regional access group",
  ownerUserId: null,
  isActive: true,
  memberUserIds: ["user-alpha", "user-bravo"],
};

function renderPage() {
  return render(
    <AppProviders initialAuthSession={previewSession}>
      <AcgAdminPage />
    </AppProviders>,
  );
}

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("removes a member from the selected access control group", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [acg] }) })
    .mockResolvedValueOnce({ ok: true })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [{ ...acg, memberUserIds: ["user-alpha"] }],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderPage();

  expect(await screen.findByRole("heading", { name: "Alpha Regional" })).toBeVisible();
  const members = within(screen.getByLabelText("Access group members"));
  expect(members.getByText("user-bravo")).toBeVisible();

  await userEvent.click(
    members.getByRole("button", { name: "Remove user-bravo from Alpha Regional" }),
  );

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/acgs/acg-alpha/members/user-bravo",
    expect.objectContaining({
      headers: { "X-CSRF-Token": "test-csrf-token" },
      method: "DELETE",
    }),
  );
});
