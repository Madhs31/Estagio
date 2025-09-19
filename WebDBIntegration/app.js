// Arquivo Principal do Servidor
const express = require('express');
const mysql = require('mysql2');
const path = require('path');
const app = express();
const port = 3000;

// Conexão com o banco de dados
const db = mysql.createConnection({
  host: 
  user: 
  password: 
  database: 
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

  db.query('SHOW TABLES LIKE ?', [tableName], (err, tableExists) => {
    if (err || tableExists.length === 0) {
      return res.render('home', { error: 'Tabela não encontrada.' });
    }

    db.query(`SELECT * FROM ?? LIMIT 100`, [tableName], (err2, rows) => {
      if (err2) return res.render('home', { error: 'Erro ao buscar dados da tabela.' });

      const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
      res.render('projects', { titulo: `Tabela: ${tableName}`, columns, projects: rows });
    });
  });
});

// ==================== ROTAS CLIENTES ====================

// Listar clientes
app.get('/clients', (req, res) => {
  const sql = `
    SELECT 
      id, Cliente, Codigo, Data_de_Inicio, Data_de_Fim, Linha_de_base, Horas_trabalhadas,
      ROUND((Horas_trabalhadas * 100.0) / Linha_de_base, 2) AS Percentual_usado,
      CASE
        WHEN (Horas_trabalhadas * 100.0) / Linha_de_base < 50 THEN 'verde'
        WHEN (Horas_trabalhadas * 100.0) / Linha_de_base < 75 THEN 'amarelo'
        ELSE 'vermelho'
      END AS Status
    FROM opt_clientes
  `;
  db.query(sql, (err, rows) => {
    if (err) {
      console.error(err);
      return res.render('clients', { titulo: 'Clientes', error: 'Erro ao buscar clientes.', clients: [] });
    }
    res.render('clients', { titulo: 'Clientes', error: null, clients: rows });
  });
});

// Formulário para adicionar cliente
app.get('/clients/new', (req, res) => {
  res.render('client_form', { titulo: 'Novo Cliente', client: null });
});

// Inserir cliente 
app.post('/clients/new', (req, res) => {
  const { Cliente, Codigo, Data_de_Inicio, Data_de_Fim, Linha_de_base } = req.body;
  const sql = `
    INSERT INTO opt_clientes (Cliente, Codigo, Data_de_Inicio, Data_de_Fim, Linha_de_base, Horas_trabalhadas)
    VALUES (?, ?, ?, ?, ?, 0)
  `;
  db.query(sql, [Cliente, Codigo, Data_de_Inicio, Data_de_Fim, Linha_de_base], (err) => {
    if (err) {
      console.error(err);
      return res.send('Erro ao adicionar cliente');
    }
    res.redirect('/clients');
  });
});

// Formulário para editar cliente
app.get('/clients/edit/:id', (req, res) => {
  const { id } = req.params;
  db.query('SELECT * FROM opt_clientes WHERE id = ?', [id], (err, rows) => {
    if (err || rows.length === 0) {
      return res.send('Cliente não encontrado');
    }
    res.render('client_form', { titulo: 'Editar Cliente', client: rows[0] });
  });
});

// Atualizar cliente (não altera Horas_trabalhadas)
app.post('/clients/edit/:id', (req, res) => {
  const { id } = req.params;
  const { Cliente, Codigo, Data_de_Inicio, Data_de_Fim, Linha_de_base } = req.body;
  const sql = `
    UPDATE opt_clientes
    SET Cliente=?, Codigo=?, Data_de_Inicio=?, Data_de_Fim=?, Linha_de_base=?
    WHERE id=?
  `;
  db.query(sql, [Cliente, Codigo, Data_de_Inicio, Data_de_Fim, Linha_de_base, id], (err) => {
    if (err) {
      console.error(err);
      return res.send('Erro ao atualizar cliente');
    }
    res.redirect('/clients');
  });
});

// Excluir cliente
app.post('/clients/delete/:id', (req, res) => {
  const { id } = req.params;
  db.query('DELETE FROM opt_clientes WHERE id=?', [id], (err) => {
    if (err) {
      console.error(err);
      return res.send('Erro ao excluir cliente');
    }
    res.redirect('/clients');
  });
});

// ==================== ROTAS DEMANDAS ====================

// Listar Demandas
app.get('/demands', (req, res) => {
  const sql = `
    SELECT
      gu.name AS ANALISTA,
      gt.name AS CLIENTE,
      COUNT(gt.id) AS QTD,
      ROUND(SUM(gt.actiontime) / 3600, 2) AS HH,
      CONCAT(COUNT(gt.id), ' ', gt.name) AS \`LINHA DE BASE\`
    FROM glpi.glpi_tickets gt
    JOIN glpi.glpi_tickets_users gtu
      ON gtu.tickets_id = gt.id
      AND gtu.type = 2               
    JOIN glpi.glpi_users gu
      ON gu.id = gtu.users_id
    WHERE gt.status <> 6
      AND gt.is_deleted = 0
    GROUP BY gu.name, gt.name
    ORDER BY gu.name, gt.name;
  `;

  db.query(sql, (err, rows) => {
    if (err) {
      console.error(err);
      return res.render('demands', { titulo: 'Demandas', error: 'Erro ao buscar demandas.', demands: [] });
    }
    res.render('demands', { titulo: 'Demandas', error: null, demands: rows });
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