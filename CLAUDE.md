# Geniza Explorer — הנחיות לקלוד

## חשוב: build.py מייצר את index.html

**אל תערוך את `index.html` ישירות.** הקובץ נוצר מחדש בכל הרצה של `build.py` (גם ב-GitHub Actions בכל push ל-main), ולכן כל שינוי ישיר בו יידרס.

כדי לשנות את תוכן הדף הראשי — ערוך את **`build.py`** בחלק שבונה את מחרוזת ה-HTML (החיפוש אחר המחרוזת הרלוונטית ב-`build.py` הוא הדרך הנכונה).

### מה נמצא איפה

| קובץ | תפקיד |
|------|--------|
| `build.py` | בונה את `index.html`, `fragment.html`, `data/search.json`, ו-`data/docs/*.json` מ-CSV של Princeton Geniza Project |
| `index.html` | **נוצר אוטומטית** — אל תערוך |
| `fragment.html` | **נוצר אוטומטית** — אל תערוך |
| `assets/style.css` | עיצוב — ניתן לעריכה |
| `assets/search.js` | לוגיקת חיפוש, מפה, ענן תגיות — ניתן לעריכה |
| `data/tags_he.json` | תגיות לכל מסמך — נוצר על ידי `apply_tags.py` |
| `data/stats.json` | סטטיסטיקות — נוצר על ידי `build.py` |

### Deploy

האתר עולה ל-GitHub Pages אוטומטית בכל push ל-`main` דרך `.github/workflows/deploy.yml`.
הזרימה: `build.py` רץ → מייצר קבצים סטטיים → נפרסים ל-Pages.

### מפה וענן תגיות

- **הוספת מקום למפה**: הוסף רשומה ל-`MAP_LOCATIONS` ב-`assets/search.js`
- **הסתרת תגית מענן התגיות**: הוסף לסט `CLOUD_SKIP` ב-`assets/search.js`
- מקומות שנמצאים ב-`MAP_LOCATIONS` צריכים להיות גם ב-`CLOUD_SKIP` (כדי שלא יופיעו פעמיים)

## פרויקט ארוך-טווח: שכתוב תיאורים בעברית עם Opus 4.7

הקיימים ב-`data/translations_he.json` הם תקצירים קצרצרים שיוצרו על ידי Haiku בריצה הראשונית. אנחנו מחליפים אותם בהדרגה בתיאורים מלאים שנכתבים מחדש על ידי Opus 4.7 דרך Claude Code. נכון לכתיבת שורות אלה: כ-2,087 הוחלפו, כ-95 "מחפירים" עוד נשארו.

**להמשיך את העבודה — השתמש בסקיל `/geniza-rewrite-batch`:**
- מוגדר ב-`.claude/skills/geniza-rewrite-batch/SKILL.md` (חלק מהריפו, זמין מכל צ'אט)
- שימוש: `/geniza-rewrite-batch [N]` — N batches × 40 ריבריטים ב-foreground, push ל-main בסוף כל batch
- הסקיל מכיל את כל הזרימה הנכונה (commit, push לסניף + main, fallback ל-merge, בדיקות זיהומים)

**קבצים רלוונטיים:**
- `rewrite_descriptions.py` — הסקריפט שעושה את העבודה (Opus 4.7 דרך `claude --print`)
- `find_translation_gaps.py` — מזהה את המסמכים עם הפער הגדול ביותר
- `.cache/rewrites_done.json` — מעקב אחרי מה שכבר נעשה (gitignored, אבל מתמשך על המכונה)

### חוק קשיח: פורמט `data/translations_he.json`

**תמיד** לכתוב את הקובץ עם `indent=2, sort_keys=True`. **לעולם לא** עם `separators=(",", ":")`.

הקובץ מכיל ~36K רשומות. בפורמט מצומצם הוא נכווץ לשורה אחת בגודל 9MB, וכל commit שמשנה רשומה אחת מציג ב-diff מחיקה של כל הקובץ + שורה חדשה אחת — בלתי ניתן לסקירה. הפורמט הקריא נותן שורה ל-ID, כך ששינוי של רשומה אחת = שורה אחת ב-diff.

זה תקף גם ב-`rewrite_descriptions.py` וגם ב-`translate.py`.
