import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "./motion-preference";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  phase: number;
};

type ParticleFieldProps = {
  className?: string;
  count?: number;
};

function createParticles(count: number, width: number, height: number): Particle[] {
  return Array.from({ length: count }, (_, index) => ({
    x: ((index * 97) % 100) * (width / 100),
    y: ((index * 53) % 100) * (height / 100),
    vx: 0.05 + ((index * 7) % 10) / 60,
    vy: -0.02 - ((index * 11) % 10) / 90,
    radius: 0.7 + ((index * 13) % 10) / 8,
    phase: (index * 37) % 360,
  }));
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  width: number,
  height: number,
  time: number,
) {
  ctx.clearRect(0, 0, width, height);
  for (const particle of particles) {
    // Modulo wrap keeps the drift continuous without per-edge branching.
    particle.x = (particle.x + particle.vx + width) % width;
    particle.y = (particle.y + particle.vy + height) % height;
    const twinkle = 0.35 + 0.3 * Math.sin(time / 900 + particle.phase);
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
    ctx.fillStyle = `rgb(94 200 248 / ${twinkle.toFixed(3)})`;
    ctx.fill();
  }
}

/**
 * Adapted from React Bits "Particles" (reactbits.dev), rewritten as a
 * dependency-free 2D canvas: softly twinkling points drifting behind content.
 * Renders a single static frame for reduced-motion users; skips entirely when
 * matchMedia is unavailable (jsdom) or no 2D context exists.
 */
export function ParticleField({ className = "", count = 56 }: ParticleFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    // No matchMedia means no way to honour reduced motion (and in jsdom no
    // canvas implementation either), so skip the ambience entirely.
    if (typeof window.matchMedia !== "function") {
      return undefined;
    }
    const canvas = canvasRef.current;
    if (canvas === null) {
      return undefined;
    }
    const ctx = canvas.getContext("2d");
    if (ctx === null) {
      return undefined;
    }
    const rect = canvas.getBoundingClientRect();
    const width = rect.width || 720;
    const height = rect.height || 540;
    const scale = window.devicePixelRatio || 1;
    canvas.width = width * scale;
    canvas.height = height * scale;
    ctx.scale(scale, scale);

    const particles = createParticles(count, width, height);
    if (prefersReducedMotion()) {
      drawFrame(ctx, particles, width, height, 0);
      return undefined;
    }
    let frame = requestAnimationFrame(function loop(time: number) {
      drawFrame(ctx, particles, width, height, time);
      frame = requestAnimationFrame(loop);
    });
    return () => cancelAnimationFrame(frame);
  }, [count]);

  return (
    <canvas aria-hidden="true" className={`particle-field ${className}`.trim()} ref={canvasRef} />
  );
}
