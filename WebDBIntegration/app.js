// Arquivo Principal do Servidor
const express = require('express');
const mysql = require('mysql2');
const path = require('path');
const app = express();
const port = 3000;

// Conexão com o banco de dados
const db = mysql.createConnection({
  host: '',
  user: '',
  password: '',
  database: ''
});

db.connect(err => {
  if (err) {
    console.error('Erro ao conectar ao MySQL:', err.stack);
    return;
  }
  console.log('Conectado ao MySQL com ID de conexão:', db.threadId);
});

// Configurações do Express
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// ==================== ROTAS ====================

// Home page: formulário para pesquisar tabela
app.get('/', (req, res) => {
  res.render('home', { error: null });
});

// Buscar tabela
app.post('/search', (req, res) => {
  const tableName = req.body.table;
  if (!tableName) return res.render('home', { error: 'Digite o nome da tabela.' });

  // Verifica se a tabela existe
  db.query('SHOW TABLES LIKE ?', [tableName], (err, tableExists) => {
    if (err || tableExists.length === 0) {
      return res.render('home', { error: 'Tabela não encontrada.' });
    }

    // Pega os dados da tabela (máximo 100 linhas)
    db.query(`SELECT * FROM ?? LIMIT 100`, [tableName], (err2, rows) => {
      if (err2) return res.render('home', { error: 'Erro ao buscar dados da tabela.' });

      // Pega os nomes das colunas
      const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
      res.render('projects', { titulo: `Tabela: ${tableName}`, columns, projects: rows });
    });
  });
});

// ==================== MIDDLEWARES ====================
app.use((req, res) => res.status(404).send('Desculpe, página não encontrada.'));
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Erro interno do servidor.');
});

// ==================== SERVIDOR ====================
app.listen(port, () => console.log(`Servidor rodando em http://localhost:${port}`));