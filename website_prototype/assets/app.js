// 悬停预览 + 首页筛选（零依赖）
(function () {
  var tip = document.getElementById('tooltip');

  document.addEventListener('mouseover', function (ev) {
    var a = ev.target.closest && ev.target.closest('a.entry-link');
    if (!a || !tip) return;
    var e = window.ENTRIES && window.ENTRIES[a.dataset.id];
    if (!e) return;
    tip.innerHTML = '<div class="t-title">' + e.title +
      '<span class="t-type">' + e.type + '词条</span></div>' +
      '<div class="t-sum">' + e.summary + '</div>';
    tip.hidden = false;
    var r = a.getBoundingClientRect();
    var x = Math.min(r.left, window.innerWidth - 360);
    var y = r.bottom + 8;
    if (y + tip.offsetHeight > window.innerHeight) y = r.top - tip.offsetHeight - 8;
    tip.style.left = Math.max(8, x) + 'px';
    tip.style.top = y + 'px';
  });
  document.addEventListener('mouseout', function (ev) {
    if (ev.target.closest && ev.target.closest('a.entry-link') && tip) tip.hidden = true;
  });

  // 首页筛选：多选，卡片须命中所有已选筛选条件
  var active = new Set();
  var chips = document.querySelectorAll('.fchip');
  function apply() {
    document.querySelectorAll('.card').forEach(function (c) {
      var ok = true;
      active.forEach(function (f) { if (!c.classList.contains(f)) ok = false; });
      c.classList.toggle('hidden', !ok);
    });
  }
  chips.forEach(function (ch) {
    ch.addEventListener('click', function () {
      var f = ch.dataset.f;
      if (!f) { active.clear(); chips.forEach(function (c) { c.classList.remove('active'); }); apply(); return; }
      if (active.has(f)) { active.delete(f); ch.classList.remove('active'); }
      else { active.add(f); ch.classList.add('active'); }
      apply();
    });
  });
})();
