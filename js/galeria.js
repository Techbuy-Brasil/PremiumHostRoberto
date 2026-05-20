function iniciarGaleria(fotosPorCategoria) {
  var modal = document.getElementById('modal');
  var container = document.getElementById('imagens-categoria');
  var fechar = document.querySelector('.fechar');
  if (!modal || !container || !fechar) return;

  function montarModal() {
    var html = '';
    for (var categoria in fotosPorCategoria) {
      var imagens = fotosPorCategoria[categoria];
      var titulo = categoria.charAt(0).toUpperCase() + categoria.slice(1);
      html += '<div class="categoria-bloco"><h3>' + titulo + '</h3><div class="categoria-imagens">';
      for (var i = 0; i < imagens.length; i++) {
        html += '<img src="' + imagens[i] + '" alt="' + categoria + '">';
      }
      html += '</div></div>';
    }
    container.innerHTML = html;
  }

  function abrirModal() { montarModal(); modal.style.display = 'block'; }
  function fecharModal() { modal.style.display = 'none'; }

  document.querySelectorAll('.galeria-airbnb img, .foto-com-overlay, .laterais-overlay').forEach(function(el) {
    el.addEventListener('click', abrirModal);
  });
  fechar.addEventListener('click', fecharModal);
  window.addEventListener('click', function(e) { if (e.target === modal) fecharModal(); });
}

function configurarReserva(_ref) {
  var telefone = _ref.telefone;
  var mensagem = _ref.mensagem;
  var botoes = document.querySelectorAll('.reserva-btn');
  botoes.forEach(function(botao) {
    botao.addEventListener('click', function() {
      var texto = encodeURIComponent('Ol\u00e1! Gostaria de reservar o im\u00f3vel: ' + mensagem);
      window.open('https://wa.me/' + telefone + '?text=' + texto, '_blank');
    });
  });
}
