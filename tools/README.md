# Pink X Intelligence Briefing - dedup tooling

Backup copies of the anti-repetition gate used by the weekly briefing task.
Restore these into `/home/user/workspace/cron_tracking/pink_x_weekly/` if the
workspace is reset.

- `dedup_engine.py`      four-layer dedup gate (URL, entity, freshness, intra-run)
- `published_index.json` index of every editorial item ever published

Rebuild the index from scratch:

    python3 dedup_engine.py build --repo /tmp/pink-x-intelligence-feed

Screen a week's candidates before writing any email copy:

    python3 dedup_engine.py check --candidates candidates_v15.json --run-date 2026-08-31 --strict

Record what shipped, after the email is sent:

    python3 dedup_engine.py record --feed feed_payload.json --run-date 2026-08-31

Inspect repetition hot spots:

    python3 dedup_engine.py stats --top 20
