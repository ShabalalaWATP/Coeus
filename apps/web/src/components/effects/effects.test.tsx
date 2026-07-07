import { act, fireEvent, render, screen } from "@testing-library/react";

import { CountUp } from "./CountUp";
import { ParticleField } from "./ParticleField";
import { SpotlightCard } from "./SpotlightCard";

type FrameCallback = (time: number) => void;

function stubMatchMedia(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches }));
}

function stubAnimationFrames() {
  const queue: FrameCallback[] = [];
  const cancelled: number[] = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameCallback) => queue.push(callback));
  vi.stubGlobal("cancelAnimationFrame", (handle: number) => cancelled.push(handle));
  return {
    cancelled,
    run(time: number) {
      const frame = queue.shift();
      if (frame) {
        act(() => frame(time));
      }
    },
    get pending() {
      return queue.length;
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("spotlight card tracks the pointer through CSS custom properties", () => {
  render(
    <SpotlightCard className="request-metric">
      <span>Total</span>
    </SpotlightCard>,
  );

  const card = screen.getByText("Total").parentElement as HTMLElement;
  fireEvent.mouseMove(card, { clientX: 40, clientY: 25 });

  expect(card.style.getPropertyValue("--spot-x")).toBe("40px");
  expect(card.style.getPropertyValue("--spot-y")).toBe("25px");
});

test("spotlight card renders without an extra class", () => {
  render(
    <SpotlightCard>
      <span>Plain</span>
    </SpotlightCard>,
  );

  expect(screen.getByText("Plain").parentElement).toHaveClass("spotlight-card");
});

test("count up renders instantly without matchMedia and when motion is reduced", () => {
  render(<CountUp value={7} />);
  expect(screen.getByText("7")).toBeInTheDocument();

  stubMatchMedia(true);
  render(<CountUp value={12} />);
  expect(screen.getByText("12")).toBeInTheDocument();
});

test("count up eases to the final value frame by frame", () => {
  stubMatchMedia(false);
  const frames = stubAnimationFrames();
  vi.spyOn(performance, "now").mockReturnValue(0);

  render(<CountUp durationMs={100} value={100} />);
  expect(screen.getByText("0")).toBeInTheDocument();

  frames.run(50);
  const midway = Number(screen.getByText(/\d+/).textContent);
  expect(midway).toBeGreaterThan(0);
  expect(midway).toBeLessThan(100);

  frames.run(200);
  expect(screen.getByText("100")).toBeInTheDocument();
  expect(frames.pending).toBe(0);
});

test("count up cancels its animation frame on unmount", () => {
  stubMatchMedia(false);
  const frames = stubAnimationFrames();
  vi.spyOn(performance, "now").mockReturnValue(0);

  const { unmount } = render(<CountUp value={40} />);
  unmount();

  expect(frames.cancelled.length).toBe(1);
});

test("particle field stays inert without matchMedia support", () => {
  const frames = stubAnimationFrames();
  const { container } = render(<ParticleField />);

  expect(container.querySelector("canvas.particle-field")).not.toBeNull();
  expect(frames.pending).toBe(0);
});

test("particle field exits early when no 2D context exists", () => {
  stubMatchMedia(true);
  const frames = stubAnimationFrames();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);

  render(<ParticleField />);

  expect(frames.pending).toBe(0);
});

function stubCanvasContext() {
  const ctx = {
    arc: vi.fn(),
    beginPath: vi.fn(),
    clearRect: vi.fn(),
    fill: vi.fn(),
    fillStyle: "",
    scale: vi.fn(),
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D,
  );
  return ctx;
}

test("particle field draws a single static frame when motion is reduced", () => {
  stubMatchMedia(true);
  const ctx = stubCanvasContext();
  const frames = stubAnimationFrames();

  render(<ParticleField count={4} />);

  expect(ctx.clearRect).toHaveBeenCalledTimes(1);
  expect(ctx.arc).toHaveBeenCalledTimes(4);
  expect(frames.pending).toBe(0);
});

test("particle field animates with device pixel scaling and stops on unmount", () => {
  stubMatchMedia(false);
  const ctx = stubCanvasContext();
  const frames = stubAnimationFrames();
  vi.stubGlobal("devicePixelRatio", 0);
  vi.spyOn(HTMLCanvasElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800,
    height: 400,
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 800,
    bottom: 400,
    toJSON: () => ({}),
  });

  const { unmount } = render(<ParticleField count={3} />);

  frames.run(16);
  frames.run(32);
  expect(ctx.clearRect).toHaveBeenCalledTimes(2);
  expect(ctx.arc).toHaveBeenCalledTimes(6);

  unmount();
  expect(frames.cancelled.length).toBe(1);
});
