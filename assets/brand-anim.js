/* ================= הנפשת הסמלים: ניגון חוזר =================
   ההנפשות עצמן יושבות ב-style.css ("הנפשת הסמלים") ורצות פעם אחת בטעינה
   בלי שום JavaScript. הקובץ הזה רק מנגן אותן שוב, בשני מקרים:
     - כשסמל נחשף מחדש אחרי שיצא לגמרי מהמסך (גלילה למטה וחזרה);
     - כל 15 שניות, לסמלים שנמצאים כרגע על המסך.
   לא מנגנים כשהלשונית ברקע, וכש"צמצום תנועה" או "עצירת אנימציות" פעילים.
   גם בלי הבדיקה הזו ה-CSS מבטל שם כל אנימציה, והניגון היה נופל על ריק.

   ניגון מחדש של אנימציית CSS: animation: none על כל אלמנט בסמל, קריאה אחת
   של רוחב שמכריחה את הדפדפן להחיל את זה, והחזרה. האנימציה מתחילה אז מאפס,
   כולל ההשהיה שלה, כך שהסדר הפנימי (קשת ואז פתח, דף אחרי דף) נשמר. */
(function () {
  var marks = document.querySelectorAll('.header-ornament .brand-mark, .kpi-svg');
  if (!marks.length || !('IntersectionObserver' in window)) return;

  var EVERY_MS = 15000;
  var reduce = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var state = new Map();   // svg → { visible, left }: left = יצא מהמסך מאז הניגון האחרון

  function still() {
    return (reduce && reduce.matches) || document.documentElement.classList.contains('a11y-still');
  }

  function replay(svg) {
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
    /* left: false — הניגון הראשון כבר רץ מה-CSS בטעינה */
    state.set(svg, { visible: false, left: false });
    io.observe(svg);
  });

  setInterval(function () {
    if (document.hidden) return;
    state.forEach(function (s, svg) { if (s.visible) replay(svg); });
  }, EVERY_MS);
})();
