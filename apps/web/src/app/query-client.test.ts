import { getQueryClient, resetQueryClientForTests } from "./query-client";

test("reuses the same query client until reset", () => {
  resetQueryClientForTests();

  const firstClient = getQueryClient();
  const secondClient = getQueryClient();

  expect(secondClient).toBe(firstClient);
});
