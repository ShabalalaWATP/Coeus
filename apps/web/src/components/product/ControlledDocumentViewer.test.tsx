import { render, screen } from "@testing-library/react";

import { ControlledDocumentViewer } from "./ControlledDocumentViewer";

test("uses an image element for safe raster previews", () => {
  render(<ControlledDocumentViewer kind="image" title="Map preview" url="blob:map" />);

  expect(screen.getByRole("img", { name: "Map preview" })).toHaveAttribute("src", "blob:map");
});

test("sandboxes non-raster previews in a non-referring frame", () => {
  render(<ControlledDocumentViewer kind="pdf" title="Report preview" url="blob:report" />);

  const frame = screen.getByTitle("Report preview");
  expect(frame).toHaveAttribute("sandbox", "");
  expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
});
