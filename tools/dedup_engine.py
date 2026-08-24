#!/usr/bin/env python3
"""
Pink X Intelligence Briefing - Dedup Engine
============================================
Replaces the unreliable free-text `topics_covered` eyeball check with a real
programmatic gate.

Four layers:
  1. URL dedup      - exact normalized URL already published -> BLOCK
  2. Entity dedup   - same entity cluster within lookback window -> BLOCK
                      unless a material change is declared
  3. Freshness gate - item publication date outside the fresh window -> BLOCK
  4. Intra-run gate - same story occupying more than one slot in THIS run -> BLOCK
                      (hero headline + headline card + stats ticker = 3x the
                       same story, which is what makes a briefing feel recycled)

Usage
-----
  # (re)build the historical index from the feed repo archive
  python3 dedup_engine.py build --repo /tmp/pink-x-intelligence-feed

  # check a candidate set before building the email
  python3 dedup_engine.py check --candidates candidates.json --run-date 2026-08-31

  # record what actually shipped (call AFTER the email is sent)
  python3 dedup_engine.py record --feed feed_payload.json --run-date 2026-08-31
"""

import json
import os
import re
import sys
import argparse
import datetime
from urllib.parse import urlsplit, urlunsplit

BASE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE, "published_index.json")

# ---------------------------------------------------------------- tuning knobs
ENTITY_LOOKBACK_DAYS = 84      # 12 weeks - an entity story is stale after this
FRESHNESS_MAX_AGE_DAYS = 14    # item must be published within this many days
URL_LOOKBACK_DAYS = 0          # 0 = forever. A URL is never republished.

# Tokens that look like proper nouns but are not entities
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "with", "from", "into", "over",
    "under", "after", "before", "this", "that", "these", "those", "new", "first",
    "second", "third", "top", "best", "most", "more", "less", "than", "then",
    "now", "just", "still", "only", "also", "how", "why", "what", "when", "who",
    "women", "woman", "female", "founder", "founders", "startup", "startups",
    "fund", "funds", "funding", "raises", "raised", "raising", "closes", "closed",
    "launch", "launches", "launched", "opens", "opened", "report", "reports",
    "data", "study", "survey", "index", "record", "records", "seed", "series",
    "round", "rounds", "deal", "deals", "grant", "grants", "accelerator",
    "program", "programme", "vc", "venture", "capital", "investor", "investors",
    "million", "billion", "percent", "share", "gap", "ceo", "ceos", "gp", "gps",
    "partner", "partners", "week", "weekly", "month", "year", "ytd", "h1", "h2",
    "q1", "q2", "q3", "q4", "us", "uk", "eu", "europe", "european", "israel",
    "israeli", "global", "world", "tech", "ai", "hits", "still", "at", "of",
    "in", "on", "to", "by", "is", "are", "was", "were", "be", "as", "its",
    "their", "her", "his", "it", "one", "two", "three", "not", "no", "all",
    "biggest", "largest", "smallest", "highest", "lowest", "up", "down",
}

MONEY_RE = re.compile(
    r"(?:[$€£₪]|USD|EUR|GBP|NIS|ILS)\s?([\d,.]+)\s?(B|M|K|bn|m|k|billion|million|thousand)?",
    re.I,
)
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")


# ------------------------------------------------------------------- utilities
def norm_url(url):
    """Canonicalise a URL so trivial variants collide."""
    if not url:
        return ""
    u = url.strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    try:
        parts = urlsplit(u)
    except ValueError:
        return u.lower()
    host = (parts.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.endswith(":443"):
        host = host[:-4]
    if host.endswith(":80"):
        host = host[:-3]
    path = re.sub(r"/+$", "", parts.path or "")
    # drop tracking params entirely - they never identify a distinct story
    return urlunsplit(("https", host, path, "", "")).lower()


def extract_entities(text):
    """
    Heuristic proper-noun extraction. Returns a normalized set.
    Picks up runs of Capitalised tokens (people, companies, funds) and
    drops generic domain vocabulary via STOPWORDS.
    """
    if not text:
        return set()
    # protect known lowercase-styled firm names before capitalisation logic
    lowered_brands = {"a16z": "a16z", "y combinator": "y combinator"}
    found = set()
    for brand, key in lowered_brands.items():
        if brand in text.lower():
            found.add(key)

    # strip markdown links to their label text
    clean = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # sentence-split so a leading capital does not create false entities
    tokens = re.findall(r"[A-Za-z0-9&'’\-\.]+", clean)

    run = []
    for i, tok in enumerate(tokens):
        bare = tok.strip(".,;:'’-")
        is_cap = bool(bare) and bare[0].isupper()
        # ALLCAPS acronyms of length>=2 count (NVCA, PitchBook is mixed case)
        if is_cap and bare.lower() not in STOPWORDS and len(bare) > 1:
            run.append(bare)
        else:
            if run:
                found.add(" ".join(run).lower())
                if len(run) > 1:
                    # also index the individual strong tokens
                    for r in run:
                        if len(r) > 3 and r.lower() not in STOPWORDS:
                            found.add(r.lower())
                run = []
    if run:
        found.add(" ".join(run).lower())
        if len(run) > 1:
            for r in run:
                if len(r) > 3 and r.lower() not in STOPWORDS:
                    found.add(r.lower())

    # normalise possessives and trailing punctuation
    out = set()
    for e in found:
        e = re.sub(r"['’]s\b", "", e).strip(" .,-")
        if e and len(e) > 2 and e not in STOPWORDS:
            out.add(e)
    return out


def extract_amounts(text):
    """Money and percentage figures - used to detect a material change."""
    if not text:
        return set()
    vals = set()
    for m in MONEY_RE.finditer(text):
        num = m.group(1).rstrip(".,")
        unit = (m.group(2) or "").lower()
        unit = {"bn": "b", "billion": "b", "million": "m", "thousand": "k"}.get(unit, unit)
        vals.add(f"{num}{unit}")
    for m in PCT_RE.finditer(text):
        vals.add(f"{m.group(1)}pct")
    return vals


def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s[:len(fmt) + 2].rstrip("Z"), fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ------------------------------------------------------------- schema adapters
def iter_story_items(feed):
    """
    Yield (title, summary, url, date) for the EDITORIAL items of a feed file,
    across all three schema generations. Programs/deadlines are intentionally
    excluded - a recurring grant deadline SHOULD repeat every week.
    """
    hw = feed.get("headline_of_the_week")
    if isinstance(hw, dict):
        yield (hw.get("title") or hw.get("headline") or "",
               hw.get("summary") or "",
               hw.get("url") or hw.get("source_url") or "",
               hw.get("date") or feed.get("run_date") or feed.get("published_at"))
    elif isinstance(hw, str) and hw.strip():
        yield (hw, "", "", feed.get("run_date") or feed.get("published_at"))

    for key in ("headlines", "top_signals"):
        for it in feed.get(key) or []:
            if not isinstance(it, dict):
                continue
            yield (it.get("title") or it.get("headline") or "",
                   it.get("summary") or "",
                   it.get("url") or it.get("source_url") or "",
                   it.get("date") or feed.get("run_date") or feed.get("published_at"))

    for it in feed.get("stats_ticker") or []:
        if not isinstance(it, dict):
            continue
        label = it.get("label") or ""
        stat = it.get("stat") or it.get("value") or ""
        yield (f"{stat} {label}".strip(), "", it.get("source_url") or "",
               feed.get("run_date") or feed.get("published_at"))


# ------------------------------------------------------------------ index I/O
def empty_index():
    return {
        "schema_version": 1,
        "built_at": None,
        "runs_indexed": [],
        "entries": [],   # {run_number, run_date, title, url, url_norm, entities, amounts, item_date, kind}
    }


def load_index():
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH) as f:
            return json.load(f)
    return empty_index()


def save_index(idx):
    idx["built_at"] = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(INDEX_PATH, "w") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)


def add_entries(idx, feed, run_date_fallback=None):
    run_number = feed.get("run_number")
    run_date = feed.get("run_date") or feed.get("published_at") or run_date_fallback
    run_date = str(parse_date(run_date) or run_date_fallback or "")
    added = 0
    seen_urls = {e["url_norm"] for e in idx["entries"] if e.get("url_norm")}
    seen_titles = {(e.get("title") or "").lower().strip() for e in idx["entries"]}
    for title, summary, url, item_date in iter_story_items(feed):
        title = (title or "").strip()
        if not title:
            continue
        un = norm_url(url)
        tl = title.lower().strip()
        if un and un in seen_urls:
            continue
        if not un and tl in seen_titles:
            continue
        blob = f"{title} {summary}"
        idx["entries"].append({
            "run_number": run_number,
            "run_date": run_date,
            "title": title,
            "url": url or "",
            "url_norm": un,
            "entities": sorted(extract_entities(blob)),
            "amounts": sorted(extract_amounts(blob)),
            "item_date": str(parse_date(item_date) or run_date),
        })
        if un:
            seen_urls.add(un)
        seen_titles.add(tl)
        added += 1
    tag = f"{run_number}:{run_date}"
    if tag not in idx["runs_indexed"]:
        idx["runs_indexed"].append(tag)
    return added


# --------------------------------------------------------------------- command
def cmd_build(args):
    repo = args.repo
    arch = os.path.join(repo, "archive")
    if not os.path.isdir(arch):
        sys.exit(f"archive dir not found: {arch}")
    idx = empty_index()
    files = sorted(
        os.listdir(arch),
        key=lambda f: (re.search(r"(\d{4}-\d{2}-\d{2})", f).group(1)
                       if re.search(r"(\d{4}-\d{2}-\d{2})", f) else f),
    )
    total = 0
    for fn in files:
        if not fn.endswith(".json"):
            continue
        path = os.path.join(arch, fn)
        try:
            feed = json.load(open(path))
        except Exception as e:
            print(f"  skip {fn}: {e}")
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})", fn)
        n = add_entries(idx, feed, run_date_fallback=m.group(1) if m else None)
        total += n
        print(f"  {fn:28s} run #{feed.get('run_number','?'):>3}  +{n} items")
    save_index(idx)
    print(f"\nIndexed {total} editorial items across {len(idx['runs_indexed'])} runs")
    print(f"Written to {INDEX_PATH}")
    return 0


def check_candidates(candidates, run_date, idx=None, verbose=True):
    """
    candidates: list of {title, summary?, url, date, material_change?}
    Returns (passed, blocked) lists.
    """
    idx = idx or load_index()
    today = parse_date(run_date) or datetime.date.today()
    entity_cutoff = today - datetime.timedelta(days=ENTITY_LOOKBACK_DAYS)

    url_map = {}
    for e in idx["entries"]:
        if e.get("url_norm"):
            url_map.setdefault(e["url_norm"], e)

    recent = []
    for e in idx["entries"]:
        d = parse_date(e.get("run_date")) or parse_date(e.get("item_date"))
        if d and d >= entity_cutoff:
            recent.append((e, set(e.get("entities") or []), set(e.get("amounts") or [])))

    passed, blocked = [], []
    seen_this_run = []   # (strong_entities, title, slot)
    # Digest slots (hero headline, subject line) legitimately summarise several
    # stories at once. They are screened for staleness only: they neither claim
    # entities for the intra-run check nor get blocked by entity repeats.
    for c in candidates:
        slot_l = str(c.get("slot", "")).lower()
        is_digest = bool(c.get("digest")) or slot_l in (
            "hero", "headline_of_the_week", "subject", "subject_line")
        # Stats-ticker items are meant to restate the figures from this week's
        # headline cards, so they skip the intra-run check but still face the
        # cross-run entity gate: a recycled story must not sneak in as a stat.
        is_restatement = bool(c.get("restates")) or slot_l.startswith(("stat", "number"))
        title = (c.get("title") or c.get("headline") or "").strip()
        summary = c.get("summary") or ""
        url = c.get("url") or c.get("source_url") or ""
        blob = f"{title} {summary}"
        un = norm_url(url)
        item_date = parse_date(c.get("date"))
        ents = extract_entities(blob)
        amts = extract_amounts(blob)
        reasons = []

        # --- layer 1: URL
        if un and un in url_map:
            prev = url_map[un]
            reasons.append(
                f"URL_ALREADY_PUBLISHED in run #{prev.get('run_number')} "
                f"({prev.get('run_date')}): {prev.get('title')[:70]}"
            )

        # --- layer 3: freshness
        if item_date is None:
            reasons.append("NO_PUBLICATION_DATE (cannot verify freshness)")
        else:
            age = (today - item_date).days
            if age > FRESHNESS_MAX_AGE_DAYS:
                reasons.append(f"STALE: published {item_date} = {age} days old "
                               f"(max {FRESHNESS_MAX_AGE_DAYS})")
            elif age < 0:
                reasons.append(f"FUTURE_DATE: {item_date}")

        # --- layer 2: entity cluster
        strong = {e for e in ents if " " in e}   # multiword = high-signal
        if strong and not is_digest:
            for prev, pents, pamts in recent:
                overlap = strong & pents
                if not overlap:
                    continue
                # material change escape hatch
                new_amounts = amts - pamts
                declared = bool(c.get("material_change"))
                if declared:
                    reasons.append(
                        f"ENTITY_REPEAT_OVERRIDDEN {sorted(overlap)} vs run "
                        f"#{prev.get('run_number')} - material_change declared: "
                        f"{c.get('material_change')}"
                    )
                elif new_amounts:
                    reasons.append(
                        f"ENTITY_REPEAT_SOFT {sorted(overlap)} vs run "
                        f"#{prev.get('run_number')} ({prev.get('run_date')}) but new "
                        f"figures {sorted(new_amounts)} - REVIEW: confirm real development"
                    )
                else:
                    reasons.append(
                        f"ENTITY_REPEAT {sorted(overlap)} already covered in run "
                        f"#{prev.get('run_number')} ({prev.get('run_date')}): "
                        f"{prev.get('title')[:70]}"
                    )
                break

        # --- layer 4: intra-run repetition (same story in >1 slot this week)
        if strong and not is_digest and not is_restatement:
            for prev_strong, prev_title, prev_slot in seen_this_run:
                ov = strong & prev_strong
                if ov:
                    reasons.append(
                        f"INTRA_RUN_DUPLICATE {sorted(ov)} already used in this same "
                        f"run by slot '{prev_slot}': {prev_title[:70]}"
                    )
                    break

        hard = [r for r in reasons if r.startswith(("URL_ALREADY", "STALE", "FUTURE_",
                                                    "ENTITY_REPEAT ", "NO_PUBLICATION",
                                                    "INTRA_RUN_DUPLICATE"))]
        rec = dict(c)
        rec["_reasons"] = reasons
        rec["_entities"] = sorted(ents)
        if hard:
            blocked.append(rec)
        else:
            passed.append(rec)
            if strong and not is_digest and not is_restatement:
                seen_this_run.append((strong, title, c.get("slot", "unnamed slot")))

    if verbose:
        print(f"Dedup gate against {len(idx['entries'])} indexed items "
              f"(entity lookback {ENTITY_LOOKBACK_DAYS}d, freshness {FRESHNESS_MAX_AGE_DAYS}d)\n")
        print(f"PASSED  : {len(passed)}")
        for p in passed:
            print(f"  OK   {p.get('title','')[:88]}")
            for r in p["_reasons"]:
                print(f"        note: {r}")
        print(f"\nBLOCKED : {len(blocked)}")
        for b in blocked:
            print(f"  X    {b.get('title','')[:88]}")
            for r in b["_reasons"]:
                print(f"        {r}")
    return passed, blocked


def cmd_check(args):
    cands = json.load(open(args.candidates))
    if isinstance(cands, dict):
        cands = cands.get("candidates") or cands.get("headlines") or []
    passed, blocked = check_candidates(cands, args.run_date)
    if args.out:
        json.dump({"passed": passed, "blocked": blocked},
                  open(args.out, "w"), indent=2, ensure_ascii=False)
        print(f"\nWritten to {args.out}")
    if blocked and args.strict:
        sys.exit(f"\nDEDUP GATE FAILED: {len(blocked)} duplicate or stale items")
    return 0


def cmd_record(args):
    idx = load_index()
    feed = json.load(open(args.feed))
    n = add_entries(idx, feed, run_date_fallback=args.run_date)
    save_index(idx)
    print(f"Recorded {n} new editorial items. Index now holds {len(idx['entries'])}.")
    return 0


def cmd_stats(args):
    idx = load_index()
    from collections import Counter
    ent = Counter()
    for e in idx["entries"]:
        for x in e.get("entities") or []:
            if " " in x:
                ent[x] += 1
    print(f"Index: {len(idx['entries'])} items, {len(idx['runs_indexed'])} runs")
    print(f"Runs: {', '.join(idx['runs_indexed'])}\n")
    print("Most repeated multiword entities:")
    for name, c in ent.most_common(args.top):
        if c < 2:
            break
        runs = sorted({e.get("run_date") for e in idx["entries"]
                       if name in (e.get("entities") or [])})
        print(f"  {c:>3}x  {name:<42} {', '.join(runs)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Pink X briefing dedup engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="rebuild index from feed repo archive")
    b.add_argument("--repo", default="/tmp/pink-x-intelligence-feed")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("check", help="screen candidate stories")
    c.add_argument("--candidates", required=True)
    c.add_argument("--run-date", required=True)
    c.add_argument("--out", default=None)
    c.add_argument("--strict", action="store_true")
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("record", help="record shipped feed into index")
    r.add_argument("--feed", required=True)
    r.add_argument("--run-date", required=True)
    r.set_defaults(func=cmd_record)

    s = sub.add_parser("stats", help="show repetition hot spots")
    s.add_argument("--top", type=int, default=30)
    s.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
