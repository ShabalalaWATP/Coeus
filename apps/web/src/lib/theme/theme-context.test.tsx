import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeProvider, useTheme } from "./theme-context";
import { render } from "@testing-library/react";

function ThemeProbe() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button type="button" onClick={toggleTheme}>
      {theme}
    </button>
  );
}

const themeStorageKey = "coeus-theme-v1";

test("uses dark theme by default and persists changes", async () => {
  const user = userEvent.setup();

  render(
    <ThemeProvider>
      <ThemeProbe />
    </ThemeProvider>,
  );

  expect(screen.getByRole("button", { name: "dark" })).toBeVisible();
  expect(window.localStorage.getItem(themeStorageKey)).toBe("dark");

  await user.click(screen.getByRole("button", { name: "dark" }));

  expect(screen.getByRole("button", { name: "light" })).toBeVisible();
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(window.localStorage.getItem(themeStorageKey)).toBe("light");
});

test("rejects theme hook usage outside provider", () => {
  const originalError = console.error;
  console.error = vi.fn();

  expect(() => render(<ThemeProbe />)).toThrow("useTheme must be used within ThemeProvider.");

  console.error = originalError;
});
