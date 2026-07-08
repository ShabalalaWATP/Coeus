import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";

import { NotificationsPopover } from "./NotificationsPopover";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const releaseNotification = {
  id: "notification-1",
  kind: "product_released",
  title: "TCK-0001 released",
  body: "Arctic assessment is now available in the Intelligence Store.",
  linkPath: "/store/products/product-1",
  read: false,
  createdAt: "2026-07-06T00:00:00Z",
};

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("shows the unread badge and opens a release notification", async () => {
  const onToggle = vi.fn();
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/read")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ...releaseNotification, read: true }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ notifications: [releaseNotification], unread: 1 }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <>
      <NotificationsPopover onToggle={onToggle} open />
      <LocationProbe />
    </>,
    "/app/requests",
  );

  expect(await screen.findByRole("button", { name: "Notifications, 1 unread" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /TCK-0001 released/ }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/notifications/notification-1/read",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(screen.getByTestId("location")).toHaveTextContent("/store/products/product-1");
  expect(onToggle).toHaveBeenCalled();
});

test("shows an inline error when marking a notification as read fails", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/read")) {
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error("no body")),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ notifications: [releaseNotification], unread: 1 }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<NotificationsPopover onToggle={vi.fn()} open />, "/app/requests");

  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001 released/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The notification could not be marked as read.",
  );
});

test("shows a retryable error when notifications cannot load", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ notifications: [releaseNotification], unread: 1 }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<NotificationsPopover onToggle={vi.fn()} open />, "/app/requests");

  expect(await screen.findByText("Notifications could not be loaded.")).toBeVisible();
  expect(screen.queryByText("No new notifications.")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Retry notifications" }));

  expect(await screen.findByRole("button", { name: /TCK-0001 released/ })).toBeVisible();
});

test("renders an empty notifications panel", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ notifications: [], unread: 0 }),
    }),
  );

  renderWithProviders(<NotificationsPopover onToggle={vi.fn()} open />, "/app/requests");

  expect(await screen.findByText("No new notifications.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Notifications" })).toBeVisible();
});
