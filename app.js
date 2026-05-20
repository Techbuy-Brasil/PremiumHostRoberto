const http = require('http');

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });

    const dados = {
        status: "online",
        projeto: "PremiumHost Roberto"
    };

    res.end(JSON.stringify(dados));
});

server.listen(PORT, () => {
    console.log(`Servidor rodando na porta ${PORT}`);
});