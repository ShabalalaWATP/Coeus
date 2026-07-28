import { screen } from "@testing-library/react";

import QcQueuePage from "./QcQueuePage";
import { baseProduct, fetchByUrl } from "./qc-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("shows the requester access warning when release metadata locks them out", async () => {
  const warned = {
    ...baseProduct,
    requesterAccessWarning:
      "Releasing with the draft metadata would prevent the requester reading " +
      "their own product: the requester belongs to none of the proposed access " +
      "control groups.",
  };
  vi.stubGlobal("fetch", vi.fn(fetchByUrl({ queueProducts: [warned] })));

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /prevent the requester reading their own product/,
  );
});
