/* ================= הנפשת הסמלים: ניגון חוזר =================
   נטען בכל דף: בדף הבית לקשת ולשלושת אייקוני המונים, ובכל דף פנימי לקשת
   שבבאנר העליון.
   ההנפשות עצמן יושבות ב-style.css ("הנפשת הסמלים") ורצות פעם אחת בטעינה
   בלי שום JavaScript. הקובץ הזה רק מנגן אותן שוב, בשני מקרים:
     - כשסמל נחשף מחדש אחרי שיצא לגמרי מהמסך (גלילה למטה וחזרה);
     - כשעברו 15 שניות מהניגון האחרון של סמל שנמצא על המסך.
   השעון הוא של כל סמל בנפרד, ומתאפס בכל ניגון: סמל שנוגן בגלילה לא יתנגן
   שוב כעבור שנייה רק משום שהגיע תורו של שעון כללי.
   לא מנגנים כשהלשונית ברקע, וכש"צמצום תנועה" או "עצירת אנימציות" פעילים.
   גם בלי הבדיקה הזו ה-CSS מבטל שם כל אנימציה, והניגון היה נופל על ריק.

   ניגון מחדש של אנימציית CSS: animation: none על כל אלמנט בסמל, קריאה אחת
   של רוחב שמכריחה את הדפדפן להחיל את זה, והחזרה. האנימציה מתחילה אז מאפס,
   כולל ההשהיה שלה, כך שהסדר הפנימי (קשת ואז פתח, דף אחרי דף) נשמר. */
(function () {
  var marks = document.querySelectorAll('.header-ornament .brand-mark, .kpi-svg, .nav-brand .brand-mark');
  if (!marks.length || !('IntersectionObserver' in window)) return;

  var EVERY_MS = 15000;
  var reduce = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  /* svg → { visible, left, last }
     left: יצא מהמסך מאז הניגון האחרון; last: מתי נוגן לאחרונה */
  var state = new Map();

  function still() {
    return (reduce && reduce.matches) || document.documentElement.classList.contains('a11y-still');
  }

  function replay(svg) {
    state.get(svg).last = performance.now();
    if (still()) return;
    var parts = svg.querySelectorAll('*');
    parts.forEach(function (el) { el.style.animation = 'none'; });
    void svg.getBoundingClientRect().width;
    parts.forEach(function (el) { el.style.animation = ''; });
  }

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      var s = state.get(e.target);
      if (e.isIntersecting) {
        if (s.left) { replay(e.target); s.left = false; }
        s.visible = true;
      } else {
        s.visible = false;
        s.left = true;
      }
    });
  });

  marks.forEach(function (svg) {
    /* הניגון הראשון כבר רץ מה-CSS בטעינה, ומשם נספרות 15 השניות.
       סמל שמחוץ למסך בטעינה יסומן left בקריאה הראשונה של ה-observer,
       ויתנגן כשיגיע אליו הקורא. */
    state.set(svg, { visible: false, left: false, last: performance.now() });
    io.observe(svg);
  });

  setInterval(function () {
    if (document.hidden) return;
    var now = performance.now();
    state.forEach(function (s, svg) {
      if (s.visible && now - s.last >= EVERY_MS) replay(svg);
    });
  }, 1000);

  /* חזרה ללשונית אחרי זמן ברקע: לא לנגן מיד את כל מה שכבר "הגיע זמנו" */
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) return;
    var now = performance.now();
    state.forEach(function (s) { s.last = Math.max(s.last, now - EVERY_MS + 3000); });
  });
})();
