import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ControlledPdfViewer } from "./ControlledPdfViewer";

const pdfMocks = vi.hoisted(() => ({
  cancel: vi.fn(),
  destroy: vi.fn(),
  getDocument: vi.fn(),
  getPage: vi.fn(),
  render: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: pdfMocks.getDocument,
}));

vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "/pdf.worker.mjs" }));

beforeEach(() => {
  vi.stubGlobal("DOMMatrix", class DOMMatrix {});
  pdfMocks.cancel.mockReset();
  pdfMocks.destroy.mockReset();
  pdfMocks.getDocument.mockReset();
  pdfMocks.getPage.mockReset();
  pdfMocks.render.mockReset();
  pdfMocks.render.mockReturnValue({ cancel: pdfMocks.cancel, promise: Promise.resolve() });
  pdfMocks.getPage.mockResolvedValue({
    getViewport: () => ({ height: 800, width: 600 }),
    render: pdfMocks.render,
  });
  pdfMocks.getDocument.mockReturnValue({
    destroy: pdfMocks.destroy,
    promise: Promise.resolve({ getPage: pdfMocks.getPage, numPages: 2 }),
  });
});

afterEach(() => vi.unstubAllGlobals());

test("renders authorised PDF pages and provides bounded navigation", async () => {
  const { unmount } = render(<ControlledPdfViewer title="Report" url="blob:report" />);

  expect(await screen.findByRole("img", { name: "Report, page 1" })).toBeVisible();
  expect(pdfMocks.getDocument).toHaveBeenCalledWith({
    stopAtErrors: true,
    url: "blob:report",
  });
  expect(screen.getByText("Page 1 of 2")).toBeVisible();
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "Next page" }));

  expect(await screen.findByRole("img", { name: "Report, page 2" })).toBeVisible();
  expect(pdfMocks.getPage).toHaveBeenLastCalledWith(2);
  expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "Previous page" }));
  expect(await screen.findByRole("img", { name: "Report, page 1" })).toBeVisible();

  unmount();
  expect(pdfMocks.destroy).toHaveBeenCalledTimes(1);
});

test("shows a safe fallback when PDF loading fails", async () => {
  pdfMocks.getDocument.mockReturnValue({
    destroy: pdfMocks.destroy,
    promise: Promise.reject(new Error("malformed")),
  });

  render(<ControlledPdfViewer title="Broken report" url="blob:broken" />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This PDF could not be rendered safely",
  );
  expect(document.querySelector('canvas[aria-label="Broken report, page 1"]')).not.toBeVisible();
});

test("shows a safe fallback when an individual page fails", async () => {
  pdfMocks.getPage.mockRejectedValue(new Error("page failed"));

  render(<ControlledPdfViewer title="Partial report" url="blob:partial" />);

  await waitFor(() => expect(pdfMocks.getPage).toHaveBeenCalledWith(1));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This PDF could not be rendered safely",
  );
});

test("fails safely when the browser lacks required canvas geometry support", async () => {
  vi.stubGlobal("DOMMatrix", undefined);

  render(<ControlledPdfViewer title="Unsupported report" url="blob:unsupported" />);

  expect(await screen.findByRole("status")).toHaveTextContent(
    "This browser cannot render the controlled PDF preview",
  );
  expect(pdfMocks.getDocument).not.toHaveBeenCalled();
});
