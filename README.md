# Pink X Intelligence Feed

Public weekly intelligence feed powering the **Pink X Intelligence Pulse** on [pinkxpwr.com](https://pinkxpwr.com).

Generated automatically every Monday by Anna's Pink X Weekly Briefing cron.

## Endpoints

- **`/latest.json`** - The top 5 signals from the most recent briefing. Use this on the homepage "Latest" box.
- **`/archive/YYYY-MM-DD.json`** - Full structured briefing per week. Use this on the dedicated `/intelligence` page (paginated).
- **`/index.json`** - Manifest of all archived weeks (sorted newest first).

## Schema (`latest.json` and `archive/*.json`)

```json
{
  "window": "2026-05-25 to 2026-06-01",
  "published_at": "2026-06-01T05:00:00Z",
  "run_number": 2,
  "top_signals": [
    {
      "rank": 1,
      "headline": "...",
      "summary": "...",
      "source_name": "...",
      "source_url": "https://...",
      "date": "2026-05-28",
      "category": "research|funding_round|grant|fund|vc_move|event|thought_leadership",
      "priority": 1
    }
  ],
  "all_signals": [ /* same shape as top_signals, full week */ ],
  "urgent_deadlines": [
    { "title": "...", "deadline": "2026-06-02", "url": "..." }
  ]
}
```

## CORS

GitHub raw URLs serve with `access-control-allow-origin: *`, so the Lovable frontend can fetch directly.

## License

Content is original analysis and curation by Pink X PowerCore.
