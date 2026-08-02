import { render, screen } from "@testing-library/react";

import { ControlledDocumentViewer } from "./ControlledDocumentViewer";

vi.mock("./ControlledPdfViewer", () => ({
  ControlledPdfViewer: ({ title }: { title: string }) => (
    <div data-testid="controlled-pdf-viewer">{title}</div>
  ),
}));

test("uses an image element for safe raster previews", () => {
  render(<ControlledDocumentViewer kind="image" title="Map preview" url="blob:map" />);

  expect(screen.getByRole("img", { name: "Map preview" })).toHaveAttribute("src", "blob:map");
});

test("renders PDFs without invoking the browser PDF plugin, including legacy metadata previews", async () => {
  render(
    <ControlledDocumentViewer
      kind="metadata"
      mimeType="application/pdf"
      title="Report preview"
      url="blob:report"
    />,
  );

  expect(await screen.findByTestId("controlled-pdf-viewer")).toHaveTextContent("Report preview");
  expect(screen.queryByTitle("Report preview")).not.toBeInTheDocument();
});

test("sandboxes other non-raster previews in a non-referring frame", () => {
  render(<ControlledDocumentViewer kind="text" title="Extract preview" url="blob:extract" />);

  const frame = screen.getByTitle("Extract preview");
  expect(frame).toHaveAttribute("sandbox", "");
  expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
});
