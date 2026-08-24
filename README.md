<div dir="rtl">

# הגניזה הקהירית

**חלון אל החיים היהודיים בימי הביניים** — ממשק עיון וחיפוש בעברית ל-35,937 מסמכים מגניזת קהיר.

🔗 **[nadaval56.github.io/geniza-explorer](https://nadaval56.github.io/geniza-explorer/)**

---

## מה זה

בבית הכנסת בן עזרא בפוסטאט — קהיר העתיקה — נצברו במשך כתשע מאות שנה מאות אלפי דפים
שאסור היה להשליכם, מפני שנשאו את שם ה׳. מתוך אדיקות דתית טהורה נבנה שם, בלי משים,
הארכיון הגדול ביותר של החיים היהודיים בימי הביניים: פסקי הלכה לצד שטרי מסחר, פיוטים
לצד רשימות מכולת, איגרות הרמב״ם לצד מכתבי יתומים.

הפרויקט הזה הוא **ממשק בעברית** מעל הנתונים הפתוחים של
[Princeton Geniza Project](https://geniza.princeton.edu). הוא אינו מאגר חדש ואינו
מחקר חדש — הוא שכבת נגישות: חיפוש חופשי, סינון, מפה, ענן נושאים, ועמוד נפרד לכל מסמך,
הכול בעברית ומימין לשמאל.

## מה יש בו

- **35,937 מסמכים**, מהם 20,505 עם תצלום דיגיטלי
- **תיאור בעברית לכל מסמך** — תרגום ועיבוד של התיאור המקורי באנגלית
- **חיפוש חופשי** בעברית ובאנגלית, כולל התאמת שמות בין השפות
- **סינון** לפי סוג מסמך, שפה, ספרייה, מאה ותקופה
- **מפה** של מקומות המוצא, וענן נושאים לחיתוך לפי תוכן
- **עמוד סטטי לכל מסמך** תחת `/d/`, שנקרא גם בלי JavaScript

## איך בונים מקומית

דורש Python 3.11+ בלבד, בלי תלויות חיצוניות.

<div dir="ltr">

```bash
python build.py                 # מוריד CSV מ-PGP, בונה הכול מאפס
python build.py --html-only     # בנייה מהירה מהנתונים המקומיים, בלי הורדה
python prerender.py             # רק עמודי המסמכים, ה-sitemap וה-robots.txt
```

</div>

לייצור מחדש של ה-favicon ותמונת התצוגה המקדימה נדרשים `pillow`, `fonttools` ו-`brotli`:

<div dir="ltr">

```bash
python make_brand_assets.py
```

</div>

הפריסה ל-GitHub Pages אוטומטית בכל push ל-`main`. פירוט מלא של מבנה הריפו — ב-[`CLAUDE.md`](CLAUDE.md).

---

## קרדיטים, רישוי ותנאי שימוש

האתר אינו הבעלים של החומרים שהוא מציג. לכל שכבה תנאים משלה:

### מטא-נתונים ותיאורים

מאת **[Princeton Geniza Project](https://geniza.princeton.edu)**, Princeton Geniza Lab,
אוניברסיטת פרינסטון. זמינים ב-[GitHub](https://github.com/princetongenizalab/pgp-metadata)
תחת [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.he).

### תיאורים בעברית

תרגום ועיבוד (adaptation) של התיאורים המקוריים באנגלית, שנוצרו בסיוע מודלי שפה עם
הגהה אנושית של מדגמים. מתוקף תנאי הרישיון השינוי מסומן ככזה בכל עמוד מסמך, והתרגומים
מופצים תחת אותם תנאים — CC BY-NC 4.0.

### תצלומים

**אינם מאוחסנים כאן.** הם נטענים ישירות מהספריות המחזיקות בכתבי היד, דרך תקן IIIF,
וכפופים לרישיון של כל מוסד — הרישיון החל מצוין מתחת לכל תצלום:

| מוסד | רישיון |
|------|--------|
| Cambridge University Library (Taylor-Schechter) | CC BY-NC 3.0 |
| Bodleian Libraries, University of Oxford | CC BY-NC 4.0 |
| Jewish Theological Seminary | CC0 / נחלת הכלל |
| John Rylands Library, Manchester | CC BY-NC-SA 4.0 |
| ספריות נוספות | ראו תנאי השימוש באתר כל ספרייה |

### גופנים

**Frank Ruhl Libre** ו-**Heebo**, תחת [SIL Open Font License 1.1](https://openfontlicense.org/).
מוגשים מהשרת של האתר — כתובות ה-IP של המבקרים אינן נשלחות לצד שלישי.

### קוד האתר

נכתב עבור הפרויקט הזה. **טרם הוגדר לו רישיון** — עד שיוגדר, כל הזכויות שמורות.

---

> ### ⚠️ שימוש לא-מסחרי בלבד
>
> רכיב ה-**NC** ברישיון CC BY-NC אוסר שימוש מסחרי בחומרים — לרבות הצבת פרסומות
> סביבם, מכירתם או שילובם במוצר בתשלום. בכל שימוש חוזר יש לתת קרדיט ל-Princeton
> Geniza Project, לקשר לרישיון, ולציין אילו שינויים נעשו.

האתר אינו אוסף נתוני מבקרים, אינו משתמש בעוגיות ואינו מפעיל שירותי ניתוח או מעקב.

מצאתם טעות בתרגום, בייחוס או בפרטי רישיון? [פתחו issue](https://github.com/nadaval56/geniza-explorer/issues).

</div>

---

<div dir="ltr">

## In English

**Geniza Explorer** is a Hebrew-language search and browsing interface for 35,937
documents from the Cairo Geniza, built on the open metadata of the
[Princeton Geniza Project](https://geniza.princeton.edu).

It adds no new scholarship. It provides a Hebrew reading layer over the existing
corpus: full-text search across Hebrew and English, faceted filtering, an origin
map, a topic cloud, and a static page per document that is readable without
JavaScript — so the collection is reachable by search engines and link previews.

**Attribution.** Metadata and descriptions are © Princeton Geniza Lab, Princeton
University, licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
The Hebrew descriptions are adaptations of the English originals and carry the same
licence. Manuscript images are not hosted here — they are loaded over IIIF from the
holding libraries and remain under each institution's own terms (see the table above).
Fonts are licensed under the SIL OFL 1.1.

**Non-commercial use only,** per the NC clause. Reuse must credit the Princeton
Geniza Project, link to the licence, and indicate what was changed.

Build with `python build.py` (Python 3.11+, no external dependencies). See
[`CLAUDE.md`](CLAUDE.md) for the repository layout.

</div>
