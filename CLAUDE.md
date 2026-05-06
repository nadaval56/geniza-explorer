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
