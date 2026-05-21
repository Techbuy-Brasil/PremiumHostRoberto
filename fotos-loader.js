function abrirModal() {
  var el = document.getElementById('modalGaleria');
  if (el) el.style.display = 'block';
}

function fecharModal() {
  var el = document.getElementById('modalGaleria');
  if (el) el.style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
  var fechar = document.querySelector('#modalGaleria .fechar');
  if (fechar) fechar.addEventListener('click', fecharModal);
  window.addEventListener('click', function(e) {
    if (e.target === document.getElementById('modalGaleria')) fecharModal();
  });
  var overlay = document.querySelector('.foto-com-overlay');
  if (overlay) overlay.addEventListener('click', abrirModal);
  document.querySelectorAll('.galeria-airbnb img').forEach(function(img) {
    img.addEventListener('click', abrirModal);
  });
});

function carregarFotosApi(propertyKey) {
  // Check localStorage first (set by admin-photos)
  try {
    var stored = JSON.parse(localStorage.getItem("ph_photos_override") || "{}");
    if (stored[propertyKey]) {
      renderizarFotos(stored[propertyKey]);
      return;
    }
  } catch(e) {}

  fetch('/api/photos/' + propertyKey)
    .then(function(r) {
      if (!r.ok) throw new Error('API indisponivel');
      return r.json();
    })
    .then(function(data) {
      if (data.categories && Object.keys(data.categories).length > 0) {
        renderizarFotos(data.categories);
      }
    })
    .catch(function() {});
}

function renderizarFotos(cats) {
  var container = document.querySelector('#modalGaleria .modal-conteudo');
  if (!container) return;
  var html = '';
  var nomes = Object.keys(cats).sort();
  nomes.forEach(function(nome) {
    var fotos = cats[nome] || [];
    if (fotos.length === 0) return;
    html += '<div class="categoria-bloco"><h3>' + nome + '</h3><div class="categoria-imagens">';
    fotos.forEach(function(url) {
      html += '<img src="' + url.replace(/"/g,'&quot;') + '" alt="' + nome.replace(/"/g,'&quot;') + '">';
    });
    html += '</div></div>';
  });
  if (html) container.innerHTML = html;
}
