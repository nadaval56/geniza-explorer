#!/usr/bin/env python3
"""
Geniza Explorer — Hebrew Description Rewrite (Opus 4.7 via Claude Code Max)

Re-writes the Hebrew description for documents that have the largest
gap between the English `description` and the (Haiku-generated) Hebrew
summary, using Claude Opus 4.7 through the Claude Code CLI (`claude
--print`). This uses the local Claude Code Max-plan authentication —
no ANTHROPIC_API_KEY required.

Strategy:
    1. Scan data/docs/, score each doc by gap (same metric as
       find_translation_gaps.py: (en_len - he_len) * (1 - ratio)).
    2. Take the top N (default 5,000), skipping any IDs already
       rewritten in a previous run.
    3. Call `claude --print --model claude-opus-4-7 …` once per doc,
       in a thread pool (configurable concurrency).
    4. As results come in, overwrite entries in
       data/translations_he.json and append IDs to
       .cache/rewrites_done.json so the next run resumes cleanly.
       (Ctrl-C is honoured — partial progress is saved.)
    5. Run `python build.py` afterwards to propagate the new HE
       descriptions into data/docs/*.json and the search index.

Usage:
    python rewrite_descriptions.py                 # top 5,000 (default)
    python rewrite_descriptions.py --top 50        # smaller smoke test
    python rewrite_descriptions.py --dry-run       # show plan only
    python rewrite_descriptions.py --workers 5     # more concurrency
"""

import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DOCS_DIR        = Path("data/docs")
TRANSLATIONS    = Path("data/translations_he.json")
REWRITES_DONE   = Path(".cache/rewrites_done.json")
ERRORS_LOG      = Path(".cache/rewrites_errors.log")

MODEL           = "claude-opus-4-7"
DEFAULT_WORKERS = 3
SAVE_EVERY      = 25      # flush progress to disk every N completions
CALL_TIMEOUT    = 240     # seconds per Opus call
MAX_RETRIES     = 3
BACKOFF_BASE    = 4       # 4s, 8s, 16s

SYSTEM_PROMPT = """אתה כותב תיאורים בעברית למסמכים מגניזת קהיר, על בסיס תיאור באנגלית מקטלוג Princeton Geniza Project.

הנחיות:
- שמור על היקף דומה לתיאור המקורי באנגלית. אל תקצר באופן משמעותי.
- אינך חייב לתרגם מילה במילה — נסח מחדש בעברית טבעית, זורמת וקריאה.
- שמור על כל המידע התוכני: תאריכים מדויקים, שמות אנשים ומקומות, פרטי האירוע, ציטוטים מהמקור, פרטים משפטיים/מסחריים/אישיים, והקשרים היסטוריים.
- דלג על מידע מידעני טכני שלא תורם לתוכן: מספרי שמורה (shelfmarks) ומיקום פיזי, שמות ספריות וקטלוגים, ראשי תיבות של מקטלגים (כגון "EMS", "MR", "AA"), והפניות ביבליוגרפיות פנימיות מפורטות (כגון "Goitein, Mediterranean Society, 3:113, 449"). אזכור כללי של חוקר ("לפי גויטיין", "לפי גיל") — מותר ורצוי כשהוא חיוני להקשר.
- שמות אנשים ומקומות: תעתיק עברי מקובל (אברהם, פוסטאט, קהיר, ירושלים, אלכסנדריה וכד').
- מונחים טכניים מהעולם הערבי-יהודי: השאר במקור או בתעתיק עברי מקובל (כתובה, גט, ת'מאם, גבלה וכד').
- כתוב אך ורק את התיאור בעברית — ללא הקדמה, ללא הערות, ללא כותרת, ללא מירכאות עוטפות."""


# ── Gap scoring (kept in sync with find_translation_gaps.py) ──────────────────
def gap_score(en_len, he_len):
    if not en_len:
        return 0.0
    ratio = he_len / en_len
    return (en_len - he_len) * (1 - min(ratio, 1.0))


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)


def select_targets(top_n, min_en, already_done):
    """Return list of {id, desc, score} for the top-N by gap score."""
    candidates = []
    for path in DOCS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        doc_id = doc.get("id")
        desc_en = (doc.get("description") or "").strip()
        desc_he = (doc.get("description_he") or "").strip()
        if not doc_id or not desc_en or len(desc_en) < min_en:
            continue
        if doc_id in already_done:
            continue
        candidates.append({
            "id": doc_id,
            "desc": desc_en,
            "score": gap_score(len(desc_en), len(desc_he)),
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:top_n]


# ── Single Claude Code call ────────────────────────────────────────────────────
def call_claude_once(desc_en, model, timeout):
    """Run `claude --print` once. Returns stdout text on success; raises on error."""
    proc = subprocess.run(
        [
            "claude",
            "--print",
            "--model", model,
            "--system-prompt", SYSTEM_PROMPT,
            "--tools", "",                  # no tool use — pure generation
            "--disable-slash-commands",
            "--no-session-persistence",
            "--output-format", "text",
        ],
        input=desc_en,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:600]
        raise RuntimeError(f"claude exit {proc.returncode}: {err}")
    text = proc.stdout.strip()
    if not text:
        raise RuntimeError("claude returned empty output")
    return text


def call_claude_with_retry(target, model, timeout, max_retries):
    """Wrapper that retries on transient failures (rate limit / overload / timeout)."""
    last_err = None
    for attempt in range(max_retries):
        try:
            return call_claude_once(target["desc"], model, timeout)
        except subprocess.TimeoutExpired as e:
            last_err = f"timeout after {timeout}s"
        except RuntimeError as e:
            last_err = str(e)
            # Don't retry on auth errors — they're not transient.
            low = last_err.lower()
            if "auth" in low or "unauthorized" in low or "forbidden" in low:
                raise
        if attempt < max_retries - 1:
            time.sleep(BACKOFF_BASE * (2 ** attempt))
    raise RuntimeError(f"failed after {max_retries} attempts: {last_err}")


# ── Orchestration ──────────────────────────────────────────────────────────────
class Progress:
    def __init__(self, translations, done_set):
        self.translations = translations
        self.done_set     = done_set
        self.lock         = threading.Lock()
        self.completed    = 0
        self.errored      = 0
        self.since_save   = 0

    def record_success(self, doc_id, text):
        with self.lock:
            self.translations[doc_id] = text
            self.done_set.add(doc_id)
            self.completed  += 1
            self.since_save += 1

    def record_error(self, doc_id, err):
        with self.lock:
            self.errored += 1
        with open(ERRORS_LOG, "a", encoding="utf-8") as f:
            f.write(f"{doc_id}\t{err}\n")

    def maybe_save(self, force=False):
        with self.lock:
            if force or self.since_save >= SAVE_EVERY:
                save_json(TRANSLATIONS, self.translations)
                save_json(REWRITES_DONE, sorted(self.done_set))
                self.since_save = 0


def run_rewrites(targets, model, workers, timeout, max_retries, progress, total):
    start = time.time()
    interrupted = False

    def worker(target):
        try:
            text = call_claude_with_retry(target, model, timeout, max_retries)
            progress.record_success(target["id"], text)
        except Exception as e:
            progress.record_error(target["id"], str(e))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(worker, t) for t in targets]
        try:
            for i, _ in enumerate(as_completed(futures), 1):
                if i % 5 == 0 or i == len(futures):
                    elapsed = time.time() - start
                    rate = i / elapsed if elapsed else 0
                    eta = (len(futures) - i) / rate if rate else 0
                    print(f"  [{i}/{len(futures)}] "
                          f"ok={progress.completed}  err={progress.errored}  "
                          f"rate={rate:.2f}/s  ETA={eta/60:.1f}m",
                          end="\r", flush=True)
                progress.maybe_save()
        except KeyboardInterrupt:
            interrupted = True
            print("\n\nInterrupted — cancelling pending work and saving progress…")
            for f in futures:
                f.cancel()
    print()
    progress.maybe_save(force=True)
    return interrupted


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Rewrite Hebrew descriptions with Opus 4.7 via Claude Code")
    parser.add_argument("--top",        type=int, default=5000,
                        help="How many of the worst-gap docs to rewrite (default 5000)")
    parser.add_argument("--min-en",     type=int, default=200,
                        help="Skip docs with EN shorter than this (default 200)")
    parser.add_argument("--workers",    type=int, default=DEFAULT_WORKERS,
                        help=f"Parallel workers (default {DEFAULT_WORKERS})")
    parser.add_argument("--timeout",    type=int, default=CALL_TIMEOUT,
                        help=f"Per-call timeout in seconds (default {CALL_TIMEOUT})")
    parser.add_argument("--retries",    type=int, default=MAX_RETRIES,
                        help=f"Max retries on transient failure (default {MAX_RETRIES})")
    parser.add_argument("--model",      default=MODEL,
                        help=f"Model id (default {MODEL})")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Show plan only; no claude calls")
    args = parser.parse_args()

    translations = load_json(TRANSLATIONS, {})
    done_set = set(load_json(REWRITES_DONE, []))
    print(f"Existing translations cached: {len(translations):,}")
    print(f"Already rewritten with Opus:  {len(done_set):,}")

    print(f"\nSelecting top {args.top:,} by gap score (min EN ≥ {args.min_en} chars)…")
    targets = select_targets(args.top, args.min_en, done_set)
    if not targets:
        print("Nothing to do — all top-gap docs have already been rewritten.")
        return

    en_lens = [len(t["desc"]) for t in targets]
    print(f"  → {len(targets):,} docs queued")
    print(f"  EN length:  min={min(en_lens):,}  max={max(en_lens):,}  "
          f"mean={sum(en_lens)//len(en_lens):,}  total={sum(en_lens):,} chars")
    print(f"  Model: {args.model}   Workers: {args.workers}   "
          f"Timeout: {args.timeout}s")

    if args.dry_run:
        print("\n[dry-run] no claude calls made.")
        for t in targets[:5]:
            print(f"  id={t['id']:>6}  en_len={len(t['desc']):>5}  "
                  f"score={t['score']:>7.0f}")
        return

    print()
    progress = Progress(translations, done_set)
    interrupted = run_rewrites(
        targets, args.model, args.workers, args.timeout, args.retries,
        progress, total=len(targets),
    )

    print(f"\nCompleted: {progress.completed:,}   "
          f"Errors: {progress.errored:,}   "
          f"Total rewritten so far: {len(done_set):,}")
    if progress.errored:
        print(f"  See {ERRORS_LOG} for failed IDs.")
    if interrupted:
        print("\nRun the same command again to resume from where you stopped.")
    _next_steps()


def _next_steps():
    print()
    print("Next steps:")
    print("  python build.py          # propagate new HE into data/docs/*.json")
    print("  git add data/translations_he.json .cache/rewrites_done.json")
    print("  git commit -m 'Rewrite Hebrew descriptions with Opus 4.7'")
    print("  git push")


if __name__ == "__main__":
    main()
