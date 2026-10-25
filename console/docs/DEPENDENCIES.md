# Frontend dependency selection

All versions below are exact in `package.json` and locked in `package-lock.json`. Publish timestamps were checked against npm registry metadata on 2026-10-25. Every selected version predates implementation by at least 14 days. `npm ci`, the production build, and the test suite completed without `--force`.

| Direct dependency | Version | Published (UTC) |
| --- | ---: | --- |
| `@react-three/drei` | 10.0.0 | 2025-02-19 |
| `@react-three/fiber` | 9.0.0 | 2025-02-19 |
| `@tailwindcss/vite` | 4.1.13 | 2025-09-04 |
| `framer-motion` | 12.23.12 | 2025-07-30 |
| `lucide-react` | 0.468.0 | 2024-12-05 |
| `react` | 19.1.1 | 2025-07-28 |
| `react-dom` | 19.1.1 | 2025-07-28 |
| `recharts` | 3.10.1 | 2026-07-25 |
| `tailwindcss` | 4.1.13 | 2025-09-04 |
| `three` | 0.170.0 | 2024-10-31 |
| `@testing-library/jest-dom` | 6.8.0 | 2025-08-20 |
| `@testing-library/react` | 16.3.0 | 2025-04-02 |
| `@testing-library/user-event` | 14.6.1 | 2025-01-21 |
| `@types/node` | 22.18.6 | 2025-09-18 |
| `@types/react` | 19.1.10 | 2025-08-11 |
| `@types/react-dom` | 19.1.7 | 2025-07-29 |
| `@types/three` | 0.170.0 | 2024-11-12 |
| `@vitejs/plugin-react` | 4.7.0 | 2025-07-18 |
| `jsdom` | 26.1.0 | 2025-04-13 |
| `msw` | 2.11.0 | 2025-08-30 |
| `prettier` | 3.6.2 | 2025-06-27 |
| `typescript` | 5.9.2 | 2025-07-31 |
| `vite` | 6.4.4 | 2026-10-06 |
| `vitest` | 3.2.4 | 2025-06-17 |

## Compatibility checks

- React and React DOM are both 19.1.1. React Three Fiber 9.0.0 declares React 19 and Three `>=0.156`; Drei 10.0.0 declares React 19, Three `>=0.159`, and Fiber `^9.0.0`. The selected Three 0.170.0 satisfies both ranges.
- Recharts 3.10.1 declares React and React DOM peer ranges through React 19.
- `@vitejs/plugin-react` 4.7.0 supports Vite 4 through 7. Tailwind's Vite plugin 4.1.13 supports Vite 5.2 through 7. Vite 6.4.4 is within both ranges.
- Framer Motion 12.23.12 supports React and React DOM 18 or 19. Its lockfile pins `motion-dom` 12.23.12 and `motion-utils` 12.23.6 through exact overrides; this avoids resolving a newer `motion-dom` build with an incompatible export surface.
- Vitest 3.2.4 works with the selected jsdom and TypeScript versions. React Testing Library 16.3.0 accepts React/DOM 18 or 19 and its peer `@testing-library/dom` is present transitively in the lockfile. MSW 2.11.0 accepts TypeScript `>=4.8`.

These ranges were read from npm package metadata. The checks demonstrate install/build/test compatibility for this frontend; they do not claim broader production validation.
