import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { AppProviders } from "../app/providers";

export function renderWithProviders(ui: ReactElement, initialPath = "/app/requests"): RenderResult {
  window.history.pushState({}, "Test page", initialPath);
  return render(
    <AppProviders>
      <MemoryRouter initialEntries={[initialPath]}>{ui}</MemoryRouter>
    </AppProviders>,
  );
}
