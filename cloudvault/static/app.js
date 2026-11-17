// CSP forbids inline scripts, so small behaviours live here.
document.querySelectorAll('.fill[data-width]').forEach(function (el) {
  el.style.width = el.dataset.width + '%';
});
document.querySelectorAll('form[data-confirm]').forEach(function (form) {
  form.addEventListener('submit', function (e) {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
  });
});
