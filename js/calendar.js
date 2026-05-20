function criarCalendario({ elementId, endpoint, whatsapp }) {
  const calendarEl = document.getElementById(elementId);
  if (!calendarEl) return;

  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    locale: 'pt-br',
    height: 'auto',
    eventClick(info) {
      if (info.event.title === 'Dispon\u00edvel' && whatsapp) {
        const data = info.event.startStr;
        const msg = 'Ol\u00e1! Tenho interesse em reservar o dia ' + data + '.';
        window.open('https://wa.me/' + whatsapp + '?text=' + encodeURIComponent(msg), '_blank');
      }
    }
  });

  calendar.render();

  fetch(endpoint)
    .then(function(res) { return res.json(); })
    .then(function(diasOcupados) {
      var hoje = new Date();
      var dias = [];

      for (var i = 0; i < 180; i++) {
        var d = new Date();
        d.setDate(hoje.getDate() + i);
        var dataLocal = d.getFullYear() + '-' +
          String(d.getMonth() + 1).padStart(2, '0') + '-' +
          String(d.getDate()).padStart(2, '0');
        dias.push(dataLocal);
      }

      var eventosDisponiveis = dias
        .filter(function(d) { return !diasOcupados.includes(d); })
        .map(function(d) { return { title: 'Dispon\u00edvel', start: d, color: '#28a745' }; });

      var eventosIndisponiveis = diasOcupados.map(function(d) {
        return { title: 'Ocupado', start: d, color: '#dc3545', display: 'background' };
      });

      calendar.addEventSource(eventosDisponiveis.concat(eventosIndisponiveis));
    });
}
