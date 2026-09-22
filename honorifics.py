"""
התארים של חכמי הגניזה, ומי שמוסיף אותם לכל טקסט עברי שהאתר מציג.

גאון או רב אינו נזכר בשמו הפרטי בלבד, גם לא באזכור השני באותה פסקה: לא "סעדיה"
אלא "רב סעדיה גאון", ולא "שלמה בן יהודה" אלא "רב שלמה בן יהודה". במבואות של דפי
הנושא זה נאכף בכתיבה, אבל רוב הטקסט העברי באתר אינו נכתב כאן: 36 אלף התיאורים
ב-data/translations_he.json הם תרגום של רישום קטלוגי אנגלי, והרישום נוקב בשמות
בלי תארים. משם הם מגיעים גם לכותרות של עמודי המסמכים, שנגזרות מן התיאור.

לכן הנרמול יושב כאן ורץ בכל בנייה, ולא נעשה פעם אחת בקובץ: תיאור חדש מפרינסטון,
או תיאור שנכתב מחדש ב-rewrite_descriptions.py, מקבל את התארים בבנייה הבאה בלי
שאיש יזכור לעשות זאת.

התואר הולך אחרי המשרה. גאון נושא "רב", ומי שנשא משרה תורנית־שיפוטית נושא "רבי":
דיין, חבר וראש קהילה. דיינות היא "ידין ידין" שבסנהדרין ה ע"א, הדרגה שמעל "יורה
יורה", ודייני פוסטאט מונו מטעם הגאון או הנגיד. סופרי בית הדין, הסוחרים
והרופאים־נגידים אינם ברשימה ונזכרים בשמם, כמקובל במחקר לגבי מי שאינו דן.

שלוש מלכודות שהתגלו על החומר עצמו, וכל אחת מהן מיוצגת כאן בקוד:

  · שם אב אינו אזכור של האיש. "מבורך בן סעדיה" אינו הגאון, "חלפון בן נתנאל
    הלוי" אינו רב נתנאל הלוי, ו"מודללה בת יהודה הלוי" אינה המשורר.
  · חלק מן התיאורים כבר נושאים תואר, ובצורות רבות: רב, רבי, רבנו, ר׳, הרב,
    הגאון. הוספה עיוורת הייתה יוצרת "ר' רבי נהוראי".
  · שם פרטי חשוף אינו בהכרח האיש. "סהלאן" לבדו תופס גם את בתו של סהלאן אבן
    אלזג׳אג׳ ואת בנו של מנחם אלשעאלי, ו"נהוראי" לבדו תופס את נהוראי בן משה
    טורונג׳י. לכן הגזע כאן הוא השם המלא, גם במחיר אזכורים שלא ייתפסו.
"""
import re

HEB = "א-ת"

# גזע → התואר שלפניו. רק שם שזיהויו באוסף חד־משמעי נכנס לכאן: "האי" למשל הוא
# גם מילה עברית, ו"סהלאן" לבדו הוא יותר מאדם אחד.
TITLES = {
    # גאוני בבל, ארץ ישראל ומצרים
    "סעדיה גאון":        "רב",
    "סעדיה בן יוסף אלפיומי": "רב",
    "שרירא":             "רב",
    "שלמה בן יהודה":     "רב",
    "שלמה גאון":         "רב",
    "שלמה הכהן גאון":    "רב",
    "דניאל בן עזריה":    "רב",
    "נתנאל הלוי":        "רב",
    # ראשי קהילה, חברים ודיינים
    "אפרים בן שמריה":    "רבי",
    "סהלאן בן אברהם":    "רבי",
    "סהלאן ב' אברהם":    "רבי",
    "סהלאן ב׳ אברהם":    "רבי",
    "עלי בן עמרם":       "רבי",
    "נהוראי בן נסים":    "רבי",
    "נהוראי בן ניסים":   "רבי",
    "שלמה בן אליהו":     "רבי",
    "אליהו בן זכריה":    "רבי",
    # חכמים
    "יהודה הלוי":        "רבי",
    'אברהם בן הרמב"ם':   "רבי",
    "אברהם בן הרמב״ם":   "רבי",
}

# המילה שלפני השם. אם היא אחת מאלה, השם הוא שם אב ולא אזכור של האיש.
PATRONYMICS = {"בן", "בר", "בת", "אבן", "ב'", "ב׳", 'ב"ר', "ב״ר"}

# ואם היא אחת מאלה, התואר כבר שם ואין להוסיף שני.
EXISTING_TITLES = {
    "רב", "רבי", "רבנו", "רבינו", "ר'", "ר׳", "הרב", "הרבי",
    "גאון", "הגאון", "גאונים", "הגאונים", "מרן", "אדוננו", "אדונינו",
}

# הצורה המקוצרת של שם שכבר נזכר במלואו ובתוארו באותו תיאור. "סעדיה" לבדו אינו
# נכנס ל-TITLES ולעולם לא ייכנס: באוסף הוא גם חזן בפוסטאט ("סעדיה החזן בן
# אברהם"), גם אישה ("סעדיה בת יוסף אל-יהודי") וגם כינוי כבוד בערבית שאינו שם
# כלל ("אלסדידה אלסעדיה") — 261 מופעים שכלל גורף היה הופך ל"רב סעדיה בת יוסף".
# אבל בתוך תיאור שכבר נקב ב"רב סעדיה גאון", האזכור השני הוא הוא, וכלל CLAUDE.md
# דורש את התואר גם בו. לכן ההרחבה הזו מותנית בטקסט ולא גלובלית.
SHORT_FORMS = {
    "סעדיה גאון": "סעדיה",
}

# מילה שבאה אחרי הצורה המקוצרת ומסגירה שהיא תחילתו של שם אחר.
NAME_CONTINUATION = {
    "הלוי", "הכהן", "החזן", "גאון", "אלפיומי", "הזקן", "הנשיא",
}

QUOTES = "\"'\u05f4\u05f3\u201c\u201d\u2018\u2019"

# אות יחס נדבקת לשם ("משלמה בן אליהו"), והתואר נכנס בין השתיים.
PREFIX = "והבלכמש"

_RULES = [
    (stem, title, re.compile(
        rf"(?<![{HEB}])(?P<pre>[{PREFIX}]{{0,2}}){re.escape(stem)}(?![{HEB}])"))
    for stem, title in TITLES.items()
]


def _preceding_word(text, end):
    """The word standing before position `end`, without a one/two-letter prefix."""
    word = text[:end].rstrip().split()[-1:]
    if not word:
        return ""
    word = word[0]
    # "לר׳" ו"מהגאונים" נושאים אות יחס לפני התואר עצמו.
    for cut in (2, 1, 0):
        candidate = word[cut:]
        if candidate in EXISTING_TITLES or candidate in PATRONYMICS:
            return candidate
    return word


_SHORT_RULES = [
    (stem, short, re.compile(
        rf"(?<![{HEB}])(?P<pre>[{PREFIX}]{{0,2}}){re.escape(short)}(?![{HEB}])"))
    for stem, short in SHORT_FORMS.items()
]


def _promote_short_forms(text):
    """Title a bare second mention, once the full name stands in the same text."""
    for stem, short, pattern in _SHORT_RULES:
        title = TITLES.get(stem)
        if not title or f"{title} {stem}" not in text:
            continue
        full = f"{title} {stem}"

        def repl(m, full=full, short=short):
            before = _preceding_word(m.string, m.start())
            if before in EXISTING_TITLES or before in PATRONYMICS:
                return m.group(0)
            after = m.string[m.end():].lstrip().split()[:1]
            if after and (after[0] in NAME_CONTINUATION
                          or after[0] in PATRONYMICS):
                return m.group(0)
            # ציטוט של השם ככתוב על כתב היד: "השם 'סעדיה' כתוב למטה".
            lhs = m.string[m.start() - 1] if m.start() else ""
            rhs = m.string[m.end():m.end() + 1]
            if lhs in QUOTES and rhs in QUOTES:
                return m.group(0)
            return f"{m.group('pre')}{full}"

        text = pattern.sub(repl, text)
    return text


def add_titles(text):
    """Insert the honorific before every bare mention of a titled figure."""
    if not text:
        return text
    for stem, title, pattern in _RULES:
        def repl(m, title=title, stem=stem):
            before = _preceding_word(m.string, m.start())
            if before in EXISTING_TITLES or before in PATRONYMICS:
                return m.group(0)
            # התואר נדחק בין אות היחס לשם, ולכן "משלמה" נעשה "מרבי שלמה".
            return f"{m.group('pre')}{title} {stem}"
        text = pattern.sub(repl, text)
    return _promote_short_forms(text)
