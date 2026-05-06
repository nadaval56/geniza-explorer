---
name: geniza-rewrite-batch
description: |-
  ALWAYS use this skill for any work on Hebrew description rewrites in this Geniza Explorer repo. Runs a batch of Opus-4.7 rewrites via rewrite_descriptions.py and pushes to main so GitHub Pages rebuilds. Trigger on requests like "/geniza-rewrite-batch", "תריץ עוד batch", "תמשיך עם הריבריטים", "תכתוב מחדש תיאורים בעברית", "continue the rewrite project", "next 40 documents", or any mention of rewrite_descriptions.py, translations_he.json, find_translation_gaps.py, or .cache/rewrites_done.json. Do NOT write a one-off script or use translate.py for this — the project has a fully-configured workflow that handles batching, the Stop-hook bug, format preservation, and the branch→main push.
---

# Geniza Rewrite Batch

You are continuing a long-running project that rewrites Hebrew descriptions for documents in the Geniza Explorer (`/home/user/geniza-explorer`). The original Hebrew was a Haiku-generated summary, far too short. We are replacing it with full-scope Opus 4.7 rewrites, working through the worst-gap documents first.

## Argument

Optional integer N = how many batches to run this turn (default 1). Each batch processes 40 documents and takes ~7-10 minutes in the foreground (within the Bash 10-min cap).

## Project state

- Working directory: `/home/user/geniza-explorer`
- Branch: `claude/detect-translation-gaps-NL6Cb` (working branch; main is the deploy target)
- Script: `rewrite_descriptions.py`
- Cache of completed IDs: `.cache/rewrites_done.json` (gitignored, persistent on this machine)
- Site auto-deploys from `main` via `.github/workflows/deploy.yml` (runs `python build.py` and pushes to GitHub Pages)

## Pre-flight (every invocation)

```bash
cd /home/user/geniza-explorer
python3 -c "import json; print('Done so far:', len(json.load(open('.cache/rewrites_done.json'))))"
git status
```

If working tree is dirty (anything uncommitted), STOP and tell the user — do not start a new batch on top of unflushed work.

## Run one batch (repeat N times)

```bash
python3 -u rewrite_descriptions.py --top 40 --workers 3 2>&1 | tail -3
```

Set the Bash `timeout` parameter to **580000** (close to the 10-min cap). The script saves progress every 25 completions and is fully resumable, so partial timeouts are safe.

Do NOT run in background (`run_in_background: true`, `nohup`, `setsid`, `&`) — Claude Code's environment kills detached processes when its session/subprocess ends. Foreground only.

## Post-batch (after each batch)

```bash
python3 -c "import json; print('Total:', len(json.load(open('.cache/rewrites_done.json'))))" && \
git add data/translations_he.json && \
git commit -m "Rewrite next 40 HE descriptions with Opus 4.7" && \
git fetch origin main && \
git push -u origin claude/detect-translation-gaps-NL6Cb 2>&1 | tail -1 && \
git push origin claude/detect-translation-gaps-NL6Cb:main 2>&1 | tail -1
```

If the final `push origin <branch>:main` fails because main has new commits (rejected: not fast-forward), recover with:
```bash
git merge origin/main --no-edit
git push -u origin claude/detect-translation-gaps-NL6Cb
git push origin claude/detect-translation-gaps-NL6Cb:main
```

Briefly tell the user the new total after each batch (one line: e.g. "**1647**.").

## Corruption check (every ~5 batches and at end)

The `--setting-sources project,local` flag in the script prevents the user-level Stop hook from corrupting outputs, but verify periodically:

```bash
python3 << 'PY'
import json
with open('data/translations_he.json', encoding='utf-8') as f: t = json.load(f)
done = json.load(open('.cache/rewrites_done.json'))
def is_corrupted(text):
    low = text.lower()
    if any(kw in low for kw in [' git', 'git ', 'git-', '-git', 'commit', 'push',
                                 'repository', 'hook', 'untracked', 'uncommitted']): return True
    if 'מאגר ה-' in text or 'מאגר git' in text or 'הודעת ה' in text: return True
    starts = ('I understand', 'I notice', 'I cannot', 'I am ', "I'm ",
              'הודעה זו', 'ההודעה', 'הודעת', 'השלמתי', 'איני יכול', 'אינני', 'לא אוכל')
    return text.strip().startswith(starts)
bad = [d for d in done if is_corrupted(t.get(d, ''))]
print(f'Total: {len(done)}  Corrupted: {len(bad)}')
PY
```

If corrupted > 0, alert the user and offer to remove the bad IDs from `rewrites_done.json` so they get redone next run.

## At the end of the session

Final summary: total rewrites + how many remain in each gap bucket.

```bash
python3 << 'PY'
import json
from pathlib import Path
done = set(json.load(open('.cache/rewrites_done.json')))
e = b25 = b50 = 0
for p in Path('data/docs').glob('*.json'):
    try: doc = json.load(open(p))
    except Exception: continue
    en = (doc.get('description') or '').strip()
    if len(en) < 200 or doc['id'] in done: continue
    he = (doc.get('description_he') or '').strip()
    r = len(he)/len(en)
    if r < 0.15: e += 1
    if r < 0.25: b25 += 1
    if r < 0.50: b50 += 1
print(f'Done: {len(done):,}   Remaining extreme (<0.15): {e:,}   <0.25: {b25:,}   <0.50: {b50:,}')
PY
```

## Hard rules

- **Token cost:** every batch consumes ~40 Opus calls from the user's Max plan. Their weekly limit resets Tuesday 8:00 (Israel time). If the user mentions running low, stop after the current batch and report.
- **Never** push to main if any commit is uncertain (corruption check failing, errors in `.cache/rewrites_errors.log`, etc.). Push to branch only and ask.
- **Never** run more batches than the user requested. If they said "/geniza-rewrite-batch 3", run 3 then stop.
- **Never** show full before/after samples unless the user asks ("דוגמאות"). They consume a lot of output tokens.
