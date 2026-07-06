# Ambient UI effects (React Bits adaptations)

Status: implemented (2026-07-06)

## Goal

Add restrained, modern motion to the interface without complicating any
workflow: ambient depth on the splash, tactile feedback on cards, and live-feeling
numbers on dashboards. Effects are decoration only; no behaviour, data flow or
control depends on them.

## Approach

Three components are adapted from the React Bits catalogue
(<https://reactbits.dev>), rewritten dependency-free because the originals pull
in `gsap`, `motion` or `ogl` and none of those is justified for ambience:

| Component | React Bits original | Adaptation |
| --- | --- | --- |
| `ParticleField` | Particles (OGL/WebGL) | 2D canvas, drifting glow points, no dependency |
| `SpotlightCard` | Spotlight Card | Pointer-tracked CSS custom properties, no ref, no dependency |
| `CountUp` | Count Up (motion) | `requestAnimationFrame` ease-out counter, no dependency |

All live in `apps/web/src/components/effects/` with styles in
`src/styles/effects.css`. Pure-CSS effects (shiny tagline sweep, active status
dot pulse, notification badge ping, staggered card rise-in) live in the same
stylesheet.

## Placement

- **Splash/login:** `ParticleField` behind the hero; shiny sweep on the
  "Task. Assess. Deliver." tagline; capability points become spotlight cards.
- **Customer dashboard and overview:** metric cards become spotlight cards and
  their values count up on load with a staggered rise-in.
- **Shell:** the notification badge pings once when unread items appear; active
  workflow status pills get a soft dot pulse.

## Accessibility and safety

- Every CSS animation is disabled by the existing global
  `prefers-reduced-motion` rule in `base.css`.
- JS-driven effects check `prefers-reduced-motion` themselves and render a
  static frame (`ParticleField`) or the final value instantly (`CountUp`).
  When `matchMedia` is unavailable (jsdom) they default to the static path, so
  tests stay deterministic.
- The particle canvas is `aria-hidden` and pointer-transparent. `CountUp`
  settles on the exact value; no assistive announcement changes mid-count
  because the containers are not live regions.
- No new dependencies, no network activity, no user input handling beyond
  pointer position on the hovered card. No security-relevant surface; the
  threat model is unchanged.

## Out of scope

- Effects on dense operational screens (queues, QC, workspace panels) beyond
  the existing hover states; those stay still by design.
- WebGL, scroll-jacking, cursor-replacement or parallax effects.
