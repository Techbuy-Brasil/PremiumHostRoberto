(function() {
  var h = document.getElementById('hamburger');
  var n = document.getElementById('nav');
  if (!h || !n) return;
  function toggle() {
    if (n.style.display === 'flex') {
      n.style.display = '';
      n.classList.remove('nav-open');
    } else {
      n.style.display = 'flex';
      n.classList.add('nav-open');
    }
  }
  h.addEventListener('click', toggle);
  h.addEventListener('touchstart', function(e) { e.preventDefault(); toggle(); });
  document.addEventListener('click', function(e) {
    if (!h.contains(e.target) && !n.contains(e.target)) {
      n.style.display = '';
      n.classList.remove('nav-open');
    }
  });
})();
