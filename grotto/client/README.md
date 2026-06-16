# Grotto — Client

The frontend for Grotto, a unified media management application. Built with React 19, TypeScript, and Vite.

## Overview

- **Framework**: React 19
- **Language**: TypeScript 5.9
- **Bundler**: Vite 8
- **API Client**: Auto-generated from the backend OpenAPI spec via `@hey-api/openapi-ts`
- **Linting**: ESLint 9 with `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh`

## Project Structure

```
client/
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── src/
│   ├── api/            # Auto-generated API client (do not edit manually)
│   ├── assets/         # Static images and SVGs
│   ├── App.tsx         # Root application component
│   ├── App.css
│   ├── main.tsx        # React entry point
│   └── index.css       # Global styles
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── eslint.config.js
└── vite.config.ts
```

## Getting Started

### Prerequisites

- Node.js 20+
- npm
- Backend running at `http://localhost:8000` (see [backend README](../backend/README.md))

### Installation

```bash
cd client
npm install
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

### Build

```bash
npm run build
```

Output is written to `dist/`. Preview the production build with:

```bash
npm run preview
```

## API Client Generation

The typed API client in `src/api/` is generated from the backend's OpenAPI schema. After making backend changes, regenerate it with:

```bash
npm run openapi-codegen
```

This reads `../backend/openapi.yaml` (written automatically on backend startup) and outputs a fully typed client to `src/api/`. Never edit files in `src/api/` directly — they will be overwritten on the next generation.

## Linting

```bash
npm run lint
```

## Further Information

- [React](https://react.dev/)
- [Vite](https://vite.dev/)
- [TypeScript](https://www.typescriptlang.org/)
- [@hey-api/openapi-ts](https://heyapi.dev/)
