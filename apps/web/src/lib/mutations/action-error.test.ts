import { ApiError } from "../api-client/client";
import { actionErrorMessage } from "./action-error";

test("uses the API error body message when the backend rejected the request", () => {
  const error = new ApiError(422, "validation_error", "Title needs at least 3 characters.");

  expect(actionErrorMessage(error, "Fallback message.")).toBe("Title needs at least 3 characters.");
});

test("falls back for generic request failures without an error body", () => {
  const error = new ApiError(500, "request_failed", "API request failed with status 500");

  expect(actionErrorMessage(error, "Fallback message.")).toBe("Fallback message.");
});

test("falls back for non-API errors", () => {
  expect(actionErrorMessage(new TypeError("fetch failed"), "Fallback message.")).toBe(
    "Fallback message.",
  );
  expect(actionErrorMessage(undefined, "Fallback message.")).toBe("Fallback message.");
});
