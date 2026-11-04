# Amazon Image Automation - Frontend Dashboard

A modern, production-ready React/Next.js dashboard for monitoring and managing the Amazon Image Automation pipeline.

## Features

- **Real-time Dashboard**: Live metrics, pipeline status, and system health
- **ASIN Management**: Browse, filter, and manage ASINs with bulk actions
- **Generation Queue**: Monitor active jobs, history, and failed jobs
- **Image Gallery**: Browse generated images with watermark status
- **Watermark Monitoring**: Track Veo/Gemini sparkle removal performance
- **Settings Management**: Full configuration UI for all pipeline components
- **Documentation**: Built-in help with search, CLI reference, and troubleshooting

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS v4 with custom design system
- **State**: Zustand + TanStack Query
- **UI Components**: Custom accessible components (Radix-inspired)
- **Charts**: Recharts for metrics visualization
- **Real-time**: Socket.io client for live updates

## Design System

### Colors
- **Brand**: Orange scale (`#f1820e` primary)
- **Surface**: Neutral grays (50-950)
- **Semantic**: Success (green), Warning (amber), Error (red), Info (blue)

### Typography
- **Sans**: Inter (UI text)
- **Mono**: JetBrains Mono (code, data)
- **Display**: Cal Sans (headings)

### Spacing & Layout
- 4px base unit
- Consistent spacing scale (0-96)
- 8px grid alignment

### Components
All components follow:
- Compound component pattern
- Full TypeScript types
- ARIA accessibility
- Dark mode support
- Framer Motion animations

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 - redirects to `/dashboard`

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── dashboard/          # Main dashboard
│   │   ├── asins/              # ASIN management
│   │   ├── generation/         # Generation queue & history
│   │   ├── images/             # Image gallery
│   │   ├── watermark/          # Watermark monitoring
│   │   ├── settings/           # Configuration
│   │   └── help/               # Documentation
│   ├── components/
│   │   ├── ui/                 # Base UI components
│   │   ├── charts/             # Data visualization
│   │   └── layout/             # Layout components
│   ├── lib/                    # Utilities, API client
│   ├── types/                  # TypeScript definitions
│   └── hooks/                  # Custom React hooks
├── public/                     # Static assets
└── tailwind.config.ts          # Design tokens
```

## Pages

| Route | Description |
|-------|-------------|
| `/dashboard` | Overview with metrics, pipeline, recent ASINs |
| `/asins` | ASIN list with search, filters, bulk actions |
| `/generation` | Queue, active jobs, history, failed jobs |
| `/images` | Grid gallery with watermark status, download |
| `/watermark` | Engine status, job log, statistics |
| `/settings` | 7-tab configuration (General, Gemini, Watermark, Scraper, Output, Notifications, Account) |
| `/help` | Searchable docs: Getting Started, CLI, Architecture, FAQ, Troubleshooting |

## API Integration

The dashboard connects to a Python backend via REST API (proxied via Next.js rewrites):

```typescript
// Example API call
const response = await fetch('/api/asins', {
  headers: { 'Content-Type': 'application/json' }
});
const data = await response.json();
```

## Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

## Scripts

```bash
npm run dev       # Development server
npm run build     # Production build
npm run start     # Production server
npm run lint      # ESLint
npm run test      # Vitest
```

## Accessibility

- WCAG 2.1 AA compliant
- Full keyboard navigation
- ARIA labels and roles
- Focus management
- Screen reader support
- Color contrast ratios

## Dark Mode

System preference detected automatically. Toggle in header.

## Testing

```bash
npm run test        # Unit tests
npm run test:watch  # Watch mode
npm run test:ui     # Vitest UI
```

## Deployment

### Docker

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Vercel

Connect GitHub repo, Vercel auto-detects Next.js.

## Contributing

1. Follow existing code style
2. Add TypeScript types for new features
3. Write tests for new components
4. Update documentation in `/help`
5. Follow conventional commits

## License

Proprietary - Brandcentral