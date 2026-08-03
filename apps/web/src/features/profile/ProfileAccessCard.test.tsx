import { screen } from "@testing-library/react";

import { ProfileAccessCard } from "./ProfileAccessCard";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

type Group = {
  code: string;
  id: string;
  isMember: boolean;
  name: string;
  applicationStatus?: "pending" | "approved" | "rejected" | "withdrawn" | null;
};

function group({ applicationStatus = null, code, id, isMember, name }: Group) {
  return {
    id,
    code,
    name,
    description: "Synthetic exercise group.",
    isMember,
    applicationStatus,
    applicationId: null,
    canReviewApplications: false,
    canManageAdmins: false,
    managerNames: [],
  };
}

function respondWith(acgs: ReturnType<typeof group>[]) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ acgs, page: 1, pageSize: 50, total: acgs.length, totalPages: 1 }),
  });
}

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("lists the groups held and links to manage them", async () => {
  vi.stubGlobal(
    "fetch",
    respondWith([
      group({ id: "1", code: "ACG-AR-GEOINT", name: "Arctic GEOINT", isMember: true }),
      group({ id: "2", code: "ACG-AF-OSINT", name: "African OSINT", isMember: false }),
    ]),
  );

  renderWithProviders(<ProfileAccessCard canViewAcgs />, "/account/profile");

  expect(await screen.findByText("ACG-AR-GEOINT")).toBeVisible();
  expect(screen.getByText("Arctic GEOINT")).toBeVisible();
  // A group the user does not hold is not their access.
  expect(screen.queryByText("ACG-AF-OSINT")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Manage/ })).toHaveAttribute("href", "/access-groups");
});

test("caps a long membership list rather than burying the page", async () => {
  const many = Array.from({ length: 14 }, (_, index) =>
    group({
      id: `acg-${index}`,
      code: `ACG-${String(index).padStart(2, "0")}`,
      name: `Group ${index}`,
      isMember: true,
    }),
  );
  vi.stubGlobal("fetch", respondWith(many));

  renderWithProviders(<ProfileAccessCard canViewAcgs />, "/account/profile");

  expect(await screen.findByText("ACG-00")).toBeVisible();
  expect(screen.getByText("ACG-08")).toBeVisible();
  expect(screen.queryByText("ACG-09")).not.toBeInTheDocument();
  expect(screen.getByText(/and 5 more/)).toBeVisible();
  expect(screen.getByRole("link", { name: "See all groups" })).toBeVisible();
});

test("reports applications still awaiting review", async () => {
  vi.stubGlobal(
    "fetch",
    respondWith([
      group({ id: "1", code: "ACG-AR-GEOINT", name: "Arctic GEOINT", isMember: true }),
      group({
        id: "2",
        code: "ACG-AF-OSINT",
        name: "African OSINT",
        isMember: false,
        applicationStatus: "pending",
      }),
    ]),
  );

  renderWithProviders(<ProfileAccessCard canViewAcgs />, "/account/profile");

  expect(await screen.findByText("1 application awaiting review.")).toBeVisible();
});

test("says plainly when no group is held", async () => {
  vi.stubGlobal("fetch", respondWith([]));

  renderWithProviders(<ProfileAccessCard canViewAcgs />, "/account/profile");

  expect(await screen.findByText(/You hold no access groups yet/)).toBeVisible();
});

test("fails closed with a bounded message", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable." } }),
    }),
  );

  renderWithProviders(<ProfileAccessCard canViewAcgs />, "/account/profile");

  expect(
    await screen.findByText("Your access groups could not be loaded.", undefined, {
      timeout: 5_000,
    }),
  ).toBeVisible();
});

test("renders nothing, and asks for nothing, without permission to view groups", () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  const { container } = renderWithProviders(
    <ProfileAccessCard canViewAcgs={false} />,
    "/account/profile",
  );

  expect(container).toBeEmptyDOMElement();
  expect(fetchMock).not.toHaveBeenCalled();
});
