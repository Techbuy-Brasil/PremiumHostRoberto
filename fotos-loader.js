function carregarFotosApi(propertyKey) {
  fetch('/api/photos/' + propertyKey)
    .then(function(r) {
      if (!r.ok) throw new Error('API indisponivel');
      return r.json();
    })
    .then(function(data) {
      var cats = data.categories;
      if (!cats || Object.keys(cats).length === 0) return;
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
    })
    .catch(function() {});
}
