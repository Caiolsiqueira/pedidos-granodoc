import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(DB_DIR, "pedidos_granodoc.db")

def get_db_path() -> str:
    return os.environ.get("GRANODOC_DB_PATH", DEFAULT_DB_PATH)

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    parent_dir = os.path.dirname(os.path.abspath(path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def hash_pin(pin: str, salt: str = "granodoc_salt_2026") -> str:
    """Hash SHA-256 with consistent salt."""
    return hashlib.sha256(f"{salt}_{pin}".encode("utf-8")).hexdigest()

def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and seed initial data if empty."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Tabela de Usuários / Setores
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_setor TEXT UNIQUE NOT NULL,
        pin_hash TEXT NOT NULL,
        nivel_acesso TEXT NOT NULL CHECK(nivel_acesso IN ('operador', 'admin')),
        icone TEXT DEFAULT 'utensils',
        descricao TEXT
    );
    """)

    # 2. Tabela de Produtos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        setor_responsavel TEXT NOT NULL,
        unidade_medida TEXT NOT NULL,
        categoria TEXT DEFAULT 'Geral',
        ativo INTEGER NOT NULL DEFAULT 1
    );
    """)

    # 3. Tabela de Pedidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        data_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'Pendente' CHECK(status IN ('Rascunho', 'Pendente', 'Aprovado', 'Comprado')),
        observacoes TEXT,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    # 4. Tabela de Itens de Pedido (Catálogo)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens_pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL,
        produto_id INTEGER NOT NULL,
        quantidade_pedida REAL NOT NULL CHECK(quantidade_pedida > 0),
        FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
        FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT
    );
    """)

    # 5. Tabela de Itens Avulsos (Fora de Catálogo)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens_avulsos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL,
        descricao_item TEXT NOT NULL,
        quantidade REAL NOT NULL CHECK(quantidade > 0),
        unidade_medida TEXT NOT NULL,
        FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE
    );
    """)

    # 6. Tabela de Categorias
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        setor TEXT NOT NULL,
        UNIQUE(nome, setor)
    );
    """)

    # 7. Tabela de Junção Produto <-> Setores (Multi-praças)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produto_setores (
        produto_id INTEGER NOT NULL,
        setor TEXT NOT NULL,
        PRIMARY KEY (produto_id, setor),
        FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    # --- SEED DE USUÁRIOS PADRÃO ---
    cursor.execute("SELECT COUNT(*) as count FROM usuarios")
    if cursor.fetchone()["count"] == 0:
        usuarios_seed = [
            ("Pizza", hash_pin("1001"), "operador", "pizza", "Praça de Pizzas e Massas"),
            ("Cozinha", hash_pin("1002"), "operador", "utensils", "Cozinha Quente e Geral"),
            ("Bar", hash_pin("1003"), "operador", "cocktail", "Bebidas, Frutas e Coquetelaria"),
            ("Salão", hash_pin("1004"), "operador", "wine", "Salão, Vinhos e Atendimento"),
            ("Administracao", hash_pin("9999"), "admin", "shield-check", "Acesso Master e Gestão de Compras"),
        ]
        cursor.executemany(
            "INSERT INTO usuarios (nome_setor, pin_hash, nivel_acesso, icone, descricao) VALUES (?, ?, ?, ?, ?)",
            usuarios_seed
        )
        conn.commit()

    # --- SEED DE PRODUTOS PADRÃO ---
    cursor.execute("SELECT COUNT(*) as count FROM produtos")
    if cursor.fetchone()["count"] == 0:
        produtos_seed = [
            # Pizza (10 itens)
            ("Farinha 00 Tipo Italiana (Saco 25kg)", "Pizza", "kg", "Farinhas & Grãos"),
            ("Molho de Tomate Pelati Italiano (Lata 2.5kg)", "Pizza", "lata", "Molhos"),
            ("Queijo Mussarela Especial Fatiado", "Pizza", "kg", "Laticínios"),
            ("Queijo Mussarela de Búfala Artesanal", "Pizza", "kg", "Laticínios"),
            ("Calabresa Artesanal Curada Defumada", "Pizza", "kg", "Frios & Embutidos"),
            ("Manjericão Fresco Orgânico", "Pizza", "pct", "Hortifrúti"),
            ("Azeitona Preta Azapa Inteira", "Pizza", "kg", "Conservas"),
            ("Azeite de Oliva Extra Virgem 0.2% Acidez", "Pizza", "litro", "Azeites & Óleos"),
            ("Presunto Parma Fatiado Importado", "Pizza", "kg", "Frios & Embutidos"),
            ("Queijo Gorgonzola Dolce DOP", "Pizza", "kg", "Laticínios"),

            # Cozinha (10 itens)
            ("Filé Mignon Bovino Limpo Inteiro", "Cozinha", "kg", "Carnes & Aves"),
            ("Peito de Frango Resfriado em Cubos", "Cozinha", "kg", "Carnes & Aves"),
            ("Arroz Arbório Especial para Risoto (1kg)", "Cozinha", "kg", "Grãos & Cereais"),
            ("Creme de Leite Fresco Pasteurizado (1L)", "Cozinha", "litro", "Laticínios"),
            ("Manteiga Extra Primeira Qualidade com Sal", "Cozinha", "kg", "Laticínios"),
            ("Cebola Roxa Selecionada", "Cozinha", "kg", "Hortifrúti"),
            ("Alho Branco Descascado Dentes (1kg)", "Cozinha", "kg", "Hortifrúti"),
            ("Sal Grosso Marinho Iodado (1kg)", "Cozinha", "kg", "Temperos & Especiarias"),
            ("Caldo de Legumes Artesanal Concentrado", "Cozinha", "litro", "Bases & Caldos"),
            ("Batata Asterix Especial Fritura", "Cozinha", "kg", "Hortifrúti"),

            # Bar (10 itens)
            ("Gin Tanqueray London Dry 750ml", "Bar", "garrafa", "Destilados"),
            ("Vodka Absolut Original 1L", "Bar", "garrafa", "Destilados"),
            ("Xarope de Açúcar Cristal Simples 1:1", "Bar", "litro", "Xaropes & Caldas"),
            ("Água Tônica Antarctica Lata 350ml", "Bar", "lata", "Não Alcoólicos"),
            ("Refrigerante Coca-Cola Original Lata 350ml", "Bar", "lata", "Não Alcoólicos"),
            ("Limão Siciliano Fresco", "Bar", "kg", "Frutas Frescas"),
            ("Limão Taiti Selecionado", "Bar", "kg", "Frutas Frescas"),
            ("Hortelã Fresca Orgânica", "Bar", "pct", "Ervas & Especiarias"),
            ("Energético Red Bull Energy Drink 250ml", "Bar", "lata", "Não Alcoólicos"),
            ("Rum Bacardi Carta Blanca 980ml", "Bar", "garrafa", "Destilados"),

            # Salão (10 itens)
            ("Vinho Tinto Malbec Reserva Mendoza 750ml", "Salão", "garrafa", "Vinhos Tintos"),
            ("Vinho Tinto Cabernet Sauvignon Gran Reserva 750ml", "Salão", "garrafa", "Vinhos Tintos"),
            ("Vinho Branco Sauvignon Blanc Vale de Casablanca 750ml", "Salão", "garrafa", "Vinhos Brancos"),
            ("Espumante Brut Método Charmat Serra Gaúcha 750ml", "Salão", "garrafa", "Espumantes"),
            ("Vinho Tinto Chianti Clássico DOCG Toscana 750ml", "Salão", "garrafa", "Vinhos Tintos"),
            ("Vinho Rosé Côtes de Provence 750ml", "Salão", "garrafa", "Vinhos Rosés"),
            ("Taças de Cristal Degustação 450ml", "Salão", "un", "Acessórios & Bar"),
            ("Cápsulas de Gás Argônio para Sistema Coravin", "Salão", "un", "Acessórios & Bar"),
            ("Decanter de Cristal Soprado 1500ml", "Salão", "un", "Acessórios & Bar"),
            ("Champanheira Inox Grande para 4 Garrafas", "Salão", "un", "Acessórios & Bar"),
        ]
        cursor.executemany(
            "INSERT INTO produtos (nome, setor_responsavel, unidade_medida, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
            produtos_seed
        )
        conn.commit()

    # --- MIGRAÇÃO AUTOMÁTICA: SOMMELIER -> SALÃO (Bancos já existentes) ---
    cursor.execute("""
        UPDATE usuarios 
        SET nome_setor = 'Salão', 
            descricao = 'Salão, Vinhos e Atendimento' 
        WHERE nome_setor = 'Sommelier';
    """)
    cursor.execute("""
        UPDATE categorias 
        SET setor = 'Salão' 
        WHERE setor = 'Sommelier';
    """)
    cursor.execute("""
        UPDATE produto_setores 
        SET setor = 'Salão' 
        WHERE setor = 'Sommelier';
    """)
    cursor.execute("SELECT id, setor_responsavel FROM produtos WHERE setor_responsavel LIKE '%Sommelier%'")
    for r in cursor.fetchall():
        new_setores = r["setor_responsavel"].replace("Sommelier", "Salão")
        cursor.execute("UPDATE produtos SET setor_responsavel = ? WHERE id = ?", (new_setores, r["id"]))
    conn.commit()

    # --- SINCRONIZAÇÃO DE PRODUTO_SETORES ---
    cursor.execute("SELECT id, setor_responsavel FROM produtos")
    existing_prods = cursor.fetchall()
    for row in existing_prods:
        pid = row["id"]
        setores_str = row["setor_responsavel"] or ""
        for s in [sec.strip() for sec in setores_str.split(",") if sec.strip()]:
            cursor.execute("INSERT OR IGNORE INTO produto_setores (produto_id, setor) VALUES (?, ?)", (pid, s))
    conn.commit()

    # --- SINCRONIZAÇÃO DE CATEGORIAS ---
    cursor.execute("""
    INSERT OR IGNORE INTO categorias (nome, setor)
    SELECT DISTINCT TRIM(p.categoria), TRIM(ps.setor)
    FROM produtos p
    JOIN produto_setores ps ON ps.produto_id = p.id
    WHERE p.categoria IS NOT NULL AND TRIM(p.categoria) != '' AND TRIM(p.categoria) != 'Geral';
    """)
    # --- MIGRAÇÃO: ADICIONAR STATUS 'Rascunho' À TABELA PEDIDOS ---
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pedidos'")
    pedidos_schema_row = cursor.fetchone()
    if pedidos_schema_row and "Rascunho" not in pedidos_schema_row[0]:
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos_temp_draft_migration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                data_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'Pendente' CHECK(status IN ('Rascunho', 'Pendente', 'Aprovado', 'Comprado')),
                observacoes TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("""
            INSERT INTO pedidos_temp_draft_migration (id, usuario_id, data_hora, status, observacoes)
            SELECT id, usuario_id, data_hora, status, observacoes FROM pedidos;
        """)
        cursor.execute("DROP TABLE pedidos;")
        cursor.execute("ALTER TABLE pedidos_temp_draft_migration RENAME TO pedidos;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

    conn.close()

# --- OPERAÇÕES DE USUÁRIOS E AUTENTICAÇÃO ---

def get_user_by_id(user_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome_setor, nivel_acesso, icone, descricao FROM usuarios WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()

def get_user_by_sector(nome_setor: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE LOWER(nome_setor) = LOWER(?)", (nome_setor,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()

def get_all_users() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome_setor, nivel_acesso, icone, descricao FROM usuarios ORDER BY id ASC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def authenticate_user(nome_setor: str, pin: str) -> Optional[Dict[str, Any]]:
    """Valida o PIN de um setor específico e retorna os dados do usuário se válido."""
    user = get_user_by_sector(nome_setor)
    if not user:
        return None
    hashed = hash_pin(pin)
    if user["pin_hash"] == hashed:
        return {
            "id": user["id"],
            "nome_setor": user["nome_setor"],
            "nivel_acesso": user["nivel_acesso"],
            "icone": user["icone"],
            "descricao": user["descricao"],
        }
    return None

def authenticate_by_pin_only(pin: str) -> Optional[Dict[str, Any]]:
    """Tenta autenticar diretamente pelo PIN digitado no teclado numérico global."""
    hashed = hash_pin(pin)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome_setor, nivel_acesso, icone, descricao FROM usuarios WHERE pin_hash = ?", (hashed,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# --- OPERAÇÕES DE CATEGORIAS ---

def get_categories_by_sector(setor: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if setor and setor.lower() != 'todos':
            cur.execute("""
                SELECT c.id, c.nome, c.setor,
                       (SELECT COUNT(DISTINCT p.id) 
                        FROM produtos p 
                        LEFT JOIN produto_setores ps ON ps.produto_id = p.id
                        WHERE (LOWER(ps.setor) = LOWER(c.setor) OR instr(',' || REPLACE(LOWER(p.setor_responsavel), ' ', '') || ',', ',' || LOWER(c.setor) || ',') > 0)
                          AND LOWER(p.categoria) = LOWER(c.nome) AND p.ativo = 1) as total_produtos
                FROM categorias c
                WHERE LOWER(c.setor) = LOWER(?)
                ORDER BY c.nome ASC
            """, (setor,))
        else:
            cur.execute("""
                SELECT c.id, c.nome, c.setor,
                       (SELECT COUNT(DISTINCT p.id) 
                        FROM produtos p 
                        LEFT JOIN produto_setores ps ON ps.produto_id = p.id
                        WHERE (LOWER(ps.setor) = LOWER(c.setor) OR instr(',' || REPLACE(LOWER(p.setor_responsavel), ' ', '') || ',', ',' || LOWER(c.setor) || ',') > 0)
                          AND LOWER(p.categoria) = LOWER(c.nome) AND p.ativo = 1) as total_produtos
                FROM categorias c
                ORDER BY c.setor ASC, c.nome ASC
            """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def create_category(nome: str, setor: str) -> int:
    nome_clean = nome.strip()
    setor_clean = setor.strip()
    if not nome_clean or not setor_clean:
        raise ValueError("Nome e setor da categoria são obrigatórios.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM categorias WHERE LOWER(nome) = LOWER(?) AND LOWER(setor) = LOWER(?)", (nome_clean, setor_clean))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO categorias (nome, setor) VALUES (?, ?)", (nome_clean, setor_clean))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def delete_category(cat_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome, setor FROM categorias WHERE id = ?", (cat_id,))
        cat = cur.fetchone()
        if not cat:
            return False
        nome_cat, setor_cat = cat["nome"], cat["setor"]
        # Reassocia produtos que estavam nessa categoria para "Geral"
        cur.execute("UPDATE produtos SET categoria = 'Geral' WHERE LOWER(categoria) = LOWER(?) AND LOWER(setor_responsavel) = LOWER(?)", (nome_cat, setor_cat))
        cur.execute("DELETE FROM categorias WHERE id = ?", (cat_id,))
        conn.commit()
        return True
    finally:
        conn.close()

# --- OPERAÇÕES DE PRODUTOS ---

def get_products(setor: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT DISTINCT p.id, p.nome, p.setor_responsavel, p.unidade_medida, p.categoria, p.ativo FROM produtos p"
        params = []
        if setor and setor.lower() != "todos":
            query += " LEFT JOIN produto_setores ps ON ps.produto_id = p.id WHERE (LOWER(ps.setor) = LOWER(?) OR instr(',' || REPLACE(LOWER(p.setor_responsavel), ' ', '') || ',', ',' || LOWER(?) || ',') > 0)"
            params.extend([setor, setor])
        else:
            query += " WHERE 1=1"
        if active_only:
            query += " AND p.ativo = 1"
        query += " ORDER BY p.categoria ASC, p.nome ASC"
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]

        # Enriquecer com a lista completa de setores de cada produto
        if rows:
            prod_ids = [r["id"] for r in rows]
            placeholders = ",".join(["?"] * len(prod_ids))
            cur.execute(f"SELECT produto_id, setor FROM produto_setores WHERE produto_id IN ({placeholders})", prod_ids)
            sec_map = {}
            for s_row in cur.fetchall():
                sec_map.setdefault(s_row["produto_id"], []).append(s_row["setor"])
            for r in rows:
                if r["id"] in sec_map and sec_map[r["id"]]:
                    r["setores"] = sec_map[r["id"]]
                else:
                    r["setores"] = [s.strip() for s in (r["setor_responsavel"] or "").split(",") if s.strip()]
        return rows
    finally:
        conn.close()

def get_product_by_id(prod_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM produtos WHERE id = ?", (prod_id,))
        row = cur.fetchone()
        if not row:
            return None
        p = dict(row)
        cur.execute("SELECT setor FROM produto_setores WHERE produto_id = ?", (prod_id,))
        db_sectors = [s_row["setor"] for s_row in cur.fetchall()]
        if db_sectors:
            p["setores"] = db_sectors
        else:
            p["setores"] = [s.strip() for s in (p["setor_responsavel"] or "").split(",") if s.strip()]
        return p
    finally:
        conn.close()

def toggle_product_status(prod_id: int, ativo: bool) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE produtos SET ativo = ? WHERE id = ?", (1 if ativo else 0, prod_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def create_product(nome: str, setor: Any, unidade: str, categoria: str = "Geral") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cat_clean = categoria.strip() or "Geral"
        if isinstance(setor, (list, tuple, set)):
            setores_list = [s.strip() for s in setor if str(s).strip()]
        else:
            setores_list = [s.strip() for s in str(setor).split(",") if s.strip()]
        if not setores_list:
            setores_list = ["Geral"]

        setor_responsavel_str = ", ".join(setores_list)

        cur.execute(
            "INSERT INTO produtos (nome, setor_responsavel, unidade_medida, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
            (nome.strip(), setor_responsavel_str, unidade.strip(), cat_clean)
        )
        new_id = cur.lastrowid
        for s in setores_list:
            cur.execute("INSERT OR IGNORE INTO produto_setores (produto_id, setor) VALUES (?, ?)", (new_id, s))
            if cat_clean and cat_clean.lower() != "geral":
                cur.execute("INSERT OR IGNORE INTO categorias (nome, setor) VALUES (?, ?)", (cat_clean, s))

        conn.commit()
        return new_id
    finally:
        conn.close()

def update_product(prod_id: int, nome: str, setor: Any, unidade: str, categoria: str = "Geral") -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cat_clean = categoria.strip() or "Geral"
        if isinstance(setor, (list, tuple, set)):
            setores_list = [s.strip() for s in setor if str(s).strip()]
        else:
            setores_list = [s.strip() for s in str(setor).split(",") if s.strip()]
        if not setores_list:
            setores_list = ["Geral"]

        setor_responsavel_str = ", ".join(setores_list)

        cur.execute(
            "UPDATE produtos SET nome = ?, setor_responsavel = ?, unidade_medida = ?, categoria = ? WHERE id = ?",
            (nome.strip(), setor_responsavel_str, unidade.strip(), cat_clean, prod_id)
        )
        updated = cur.rowcount > 0

        # Atualiza a tabela de junção produto_setores
        cur.execute("DELETE FROM produto_setores WHERE produto_id = ?", (prod_id,))
        for s in setores_list:
            cur.execute("INSERT OR IGNORE INTO produto_setores (produto_id, setor) VALUES (?, ?)", (prod_id, s))
            if cat_clean and cat_clean.lower() != "geral":
                cur.execute("INSERT OR IGNORE INTO categorias (nome, setor) VALUES (?, ?)", (cat_clean, s))

        conn.commit()
        return updated
    finally:
        conn.close()

def delete_product(prod_id: int) -> Dict[str, Any]:
    """
    Exclusão segura:
    Se o insumo já foi solicitado em pedidos anteriores (itens_pedido), ele é arquivado/desativado (ativo = 0).
    Se nunca foi utilizado em nenhum pedido, é excluído permanentemente do banco de dados.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM itens_pedido WHERE produto_id = ?", (prod_id,))
        count = cur.fetchone()["count"]
        if count > 0:
            cur.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (prod_id,))
            conn.commit()
            return {
                "success": True,
                "action": "deactivated",
                "message": "Insumo desativado do catálogo para preservar o histórico de compras anteriores."
            }
        else:
            cur.execute("DELETE FROM produtos WHERE id = ?", (prod_id,))
            conn.commit()
            return {
                "success": True,
                "action": "deleted",
                "message": "Insumo excluído permanentemente com sucesso."
            }
    finally:
        conn.close()

def delete_products_batch(product_ids: List[int]) -> Dict[str, Any]:
    """
    Exclusão em lote segura:
    Para cada produto na lista de IDs:
    Se já foi solicitado em pedidos anteriores (itens_pedido), é arquivado/desativado (ativo = 0).
    Se nunca foi utilizado em nenhum pedido, é excluído permanentemente do banco de dados.
    """
    if not product_ids:
        return {"success": True, "count": 0, "deactivated": 0, "deleted": 0, "message": "Nenhum produto selecionado."}
    conn = get_connection()
    try:
        cur = conn.cursor()
        deactivated = 0
        deleted = 0
        for pid in product_ids:
            cur.execute("SELECT COUNT(*) as count FROM itens_pedido WHERE produto_id = ?", (pid,))
            row = cur.fetchone()
            count = row["count"] if row else 0
            if count > 0:
                cur.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (pid,))
                deactivated += 1
            else:
                cur.execute("DELETE FROM produtos WHERE id = ?", (pid,))
                deleted += 1
        conn.commit()
        return {
            "success": True,
            "count": len(product_ids),
            "deactivated": deactivated,
            "deleted": deleted,
            "message": f"{len(product_ids)} produtos foram processados com sucesso."
        }
    finally:
        conn.close()

def create_products_batch(produtos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Cadastra múltiplos produtos em lote de forma atômica e rápida.
    Garante também o cadastro automático de quaisquer novas categorias informadas.
    """
    if not produtos:
        return {"success": True, "count": 0}
    conn = get_connection()
    try:
        cur = conn.cursor()
        inserted_count = 0
        for p in produtos:
            nome = str(p.get("nome", "")).strip()
            setor_val = p.get("setores") or p.get("setor", "")
            if isinstance(setor_val, (list, tuple, set)):
                setores_list = [s.strip() for s in setor_val if str(s).strip()]
            else:
                setores_list = [s.strip() for s in str(setor_val).split(",") if s.strip()]
            if not setores_list:
                setores_list = ["Geral"]
            setor_str = ", ".join(setores_list)

            unidade = str(p.get("unidade_medida") or p.get("unidade") or "un").strip() or "un"
            categoria = str(p.get("categoria", "Geral")).strip() or "Geral"
            if nome:
                cur.execute(
                    "INSERT INTO produtos (nome, setor_responsavel, unidade_medida, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
                    (nome, setor_str, unidade, categoria)
                )
                new_id = cur.lastrowid
                inserted_count += 1
                for s in setores_list:
                    cur.execute("INSERT OR IGNORE INTO produto_setores (produto_id, setor) VALUES (?, ?)", (new_id, s))
                    if categoria and categoria.lower() != "geral":
                        cur.execute("INSERT OR IGNORE INTO categorias (nome, setor) VALUES (?, ?)", (categoria, s))
        conn.commit()
        return {"success": True, "count": inserted_count}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- OPERAÇÕES DE PEDIDOS ---

def create_order(
    usuario_id: int,
    itens_catalogo: List[Dict[str, Any]],
    itens_avulsos: List[Dict[str, Any]],
    observacoes: Optional[str] = None,
    data_hora_custom: Optional[str] = None
) -> int:
    """
    Cria um novo pedido com seus itens de catálogo e itens avulsos em transação atômica.
    data_hora_custom: opcional para permitir testes e simulação de datas anteriores.
    """
    if not itens_catalogo and not itens_avulsos:
        raise ValueError("O pedido deve conter pelo menos um item de catálogo ou avulso.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        dh = data_hora_custom or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute(
            "INSERT INTO pedidos (usuario_id, data_hora, status, observacoes) VALUES (?, ?, 'Pendente', ?)",
            (usuario_id, dh, observacoes.strip() if observacoes else None)
        )
        pedido_id = cur.lastrowid

        for item in itens_catalogo:
            qtd = float(item["quantidade"])
            if qtd > 0:
                cur.execute(
                    "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade_pedida) VALUES (?, ?, ?)",
                    (pedido_id, int(item["produto_id"]), qtd)
                )

        for avulso in itens_avulsos:
            qtd = float(avulso["quantidade"])
            desc = str(avulso["descricao"]).strip()
            unidade = str(avulso.get("unidade_medida", "un")).strip()
            if qtd > 0 and desc:
                cur.execute(
                    "INSERT INTO itens_avulsos (pedido_id, descricao_item, quantidade, unidade_medida) VALUES (?, ?, ?, ?)",
                    (pedido_id, desc, qtd, unidade)
                )

        conn.commit()
        return pedido_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_draft_by_sector(usuario_id: int, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retorna o rascunho em aberto de um usuário/setor para uma data específica (padrão: hoje).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        target_date = date_str or datetime.now().strftime("%Y-%m-%d")
        start = f"{target_date} 00:00:00"
        end = f"{target_date} 23:59:59"

        cur.execute("""
            SELECT p.id, p.usuario_id, p.data_hora, p.status, p.observacoes,
                   u.nome_setor, u.icone as icone_setor
            FROM pedidos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.usuario_id = ? AND p.status = 'Rascunho' AND p.data_hora BETWEEN ? AND ?
            ORDER BY p.id DESC
            LIMIT 1
        """, (usuario_id, start, end))
        row = cur.fetchone()
        if not row:
            return None

        order = dict(row)
        pid = order["id"]

        # Itens de catálogo
        cur.execute("""
            SELECT ip.id, ip.produto_id, ip.quantidade_pedida,
                   prod.nome as nome_produto, prod.unidade_medida, prod.categoria
            FROM itens_pedido ip
            JOIN produtos prod ON prod.id = ip.produto_id
            WHERE ip.pedido_id = ?
            ORDER BY prod.nome ASC
        """, (pid,))
        order["itens_catalogo"] = [dict(r) for r in cur.fetchall()]

        # Itens avulsos
        cur.execute("""
            SELECT id, descricao_item, quantidade, unidade_medida
            FROM itens_avulsos
            WHERE pedido_id = ?
            ORDER BY id ASC
        """, (pid,))
        order["itens_avulsos"] = [dict(r) for r in cur.fetchall()]

        return order
    finally:
        conn.close()

def save_order_draft(
    usuario_id: int,
    itens_catalogo: List[Dict[str, Any]],
    itens_avulsos: List[Dict[str, Any]],
    observacoes: Optional[str] = None
) -> int:
    """
    Salva ou atualiza o rascunho da praça na data atual (máximo 1 rascunho ativo por data).
    Se já houver rascunho salvo hoje, atualiza os itens e observações.
    Se não houver, insere um novo registro com status 'Rascunho'.
    """
    if not itens_catalogo and not itens_avulsos:
        raise ValueError("O rascunho deve conter pelo menos um item de catálogo ou avulso.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        today_str = datetime.now().strftime("%Y-%m-%d")
        start = f"{today_str} 00:00:00"
        end = f"{today_str} 23:59:59"

        # Verifica se já existe rascunho para este usuário hoje
        cur.execute("""
            SELECT id FROM pedidos 
            WHERE usuario_id = ? AND status = 'Rascunho' AND data_hora BETWEEN ? AND ?
            ORDER BY id DESC LIMIT 1
        """, (usuario_id, start, end))
        existing = cur.fetchone()

        obs_clean = observacoes.strip() if observacoes else None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if existing:
            pedido_id = existing["id"]
            # Atualiza dados do rascunho existente
            cur.execute(
                "UPDATE pedidos SET data_hora = ?, observacoes = ? WHERE id = ?",
                (now_str, obs_clean, pedido_id)
            )
            # Remove itens antigos para regravar
            cur.execute("DELETE FROM itens_pedido WHERE pedido_id = ?", (pedido_id,))
            cur.execute("DELETE FROM itens_avulsos WHERE pedido_id = ?", (pedido_id,))
        else:
            # Cria novo rascunho
            cur.execute(
                "INSERT INTO pedidos (usuario_id, data_hora, status, observacoes) VALUES (?, ?, 'Rascunho', ?)",
                (usuario_id, now_str, obs_clean)
            )
            pedido_id = cur.lastrowid

        # Insere itens de catálogo
        for item in itens_catalogo:
            qtd = float(item["quantidade"])
            if qtd > 0:
                cur.execute(
                    "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade_pedida) VALUES (?, ?, ?)",
                    (pedido_id, int(item["produto_id"]), qtd)
                )

        # Insere itens avulsos
        for avulso in itens_avulsos:
            qtd = float(avulso["quantidade"])
            desc = str(avulso["descricao"]).strip()
            unidade = str(avulso.get("unidade_medida", "un")).strip()
            if qtd > 0 and desc:
                cur.execute(
                    "INSERT INTO itens_avulsos (pedido_id, descricao_item, quantidade, unidade_medida) VALUES (?, ?, ?, ?)",
                    (pedido_id, desc, qtd, unidade)
                )

        conn.commit()
        return pedido_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def finalize_draft_or_create_order(
    usuario_id: int,
    itens_catalogo: List[Dict[str, Any]],
    itens_avulsos: List[Dict[str, Any]],
    observacoes: Optional[str] = None,
    draft_id: Optional[int] = None
) -> int:
    """
    Finaliza e envia um pedido para a administração com status 'Pendente'.
    Se existia um rascunho aberto (informado por draft_id ou verificado para a data de hoje),
    atualiza o registro do rascunho para status 'Pendente', atualiza itens e horário.
    Caso contrário, cria um novo pedido diretamente.
    """
    if not itens_catalogo and not itens_avulsos:
        raise ValueError("O pedido deve conter pelo menos um item de catálogo ou avulso.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        today_str = datetime.now().strftime("%Y-%m-%d")
        start = f"{today_str} 00:00:00"
        end = f"{today_str} 23:59:59"

        target_draft_id = draft_id
        if not target_draft_id:
            cur.execute("""
                SELECT id FROM pedidos 
                WHERE usuario_id = ? AND status = 'Rascunho' AND data_hora BETWEEN ? AND ?
                ORDER BY id DESC LIMIT 1
            """, (usuario_id, start, end))
            row = cur.fetchone()
            if row:
                target_draft_id = row["id"]

        obs_clean = observacoes.strip() if observacoes else None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if target_draft_id:
            # Converte o rascunho existente em Pendente
            cur.execute(
                "UPDATE pedidos SET status = 'Pendente', data_hora = ?, observacoes = ? WHERE id = ?",
                (now_str, obs_clean, target_draft_id)
            )
            pedido_id = target_draft_id
            # Atualiza itens
            cur.execute("DELETE FROM itens_pedido WHERE pedido_id = ?", (pedido_id,))
            cur.execute("DELETE FROM itens_avulsos WHERE pedido_id = ?", (pedido_id,))
        else:
            cur.execute(
                "INSERT INTO pedidos (usuario_id, data_hora, status, observacoes) VALUES (?, ?, 'Pendente', ?)",
                (usuario_id, now_str, obs_clean)
            )
            pedido_id = cur.lastrowid

        for item in itens_catalogo:
            qtd = float(item["quantidade"])
            if qtd > 0:
                cur.execute(
                    "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade_pedida) VALUES (?, ?, ?)",
                    (pedido_id, int(item["produto_id"]), qtd)
                )

        for avulso in itens_avulsos:
            qtd = float(avulso["quantidade"])
            desc = str(avulso["descricao"]).strip()
            unidade = str(avulso.get("unidade_medida", "un")).strip()
            if qtd > 0 and desc:
                cur.execute(
                    "INSERT INTO itens_avulsos (pedido_id, descricao_item, quantidade, unidade_medida) VALUES (?, ?, ?, ?)",
                    (pedido_id, desc, qtd, unidade)
                )

        conn.commit()
        return pedido_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_order_status(pedido_id: int, new_status: str) -> bool:
    if new_status not in ("Rascunho", "Pendente", "Aprovado", "Comprado"):
        raise ValueError(f"Status inválido: {new_status}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE pedidos SET status = ? WHERE id = ?", (new_status, pedido_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def update_orders_status_by_date(date_str: str, new_status: str) -> int:
    """
    Atualiza o status de todos os pedidos ativos de uma data especificada (Aba 2 - Consolidação).
    Ignora pedidos com status 'Rascunho'.
    Retorna a quantidade de pedidos atualizados.
    """
    if new_status not in ("Pendente", "Aprovado", "Comprado"):
        raise ValueError(f"Status inválido: {new_status}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        start = f"{date_str} 00:00:00"
        end = f"{date_str} 23:59:59"
        cur.execute("""
            UPDATE pedidos 
            SET status = ? 
            WHERE (DATE(data_hora) = ? OR data_hora BETWEEN ? AND ?) AND status != 'Rascunho'
        """, (new_status, date_str, start, end))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()

def get_order_details(pedido_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.usuario_id, p.data_hora, p.status, p.observacoes,
                   u.nome_setor, u.icone as icone_setor
            FROM pedidos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.id = ?
        """, (pedido_id,))
        order_row = cur.fetchone()
        if not order_row:
            return None

        order = dict(order_row)

        # Itens de catálogo
        cur.execute("""
            SELECT ip.id, ip.produto_id, ip.quantidade_pedida,
                   prod.nome as nome_produto, prod.unidade_medida, prod.categoria
            FROM itens_pedido ip
            JOIN produtos prod ON prod.id = ip.produto_id
            WHERE ip.pedido_id = ?
            ORDER BY prod.nome ASC
        """, (pedido_id,))
        order["itens_catalogo"] = [dict(r) for r in cur.fetchall()]

        # Itens avulsos
        cur.execute("""
            SELECT id, descricao_item, quantidade, unidade_medida
            FROM itens_avulsos
            WHERE pedido_id = ?
            ORDER BY id ASC
        """, (pedido_id,))
        order["itens_avulsos"] = [dict(r) for r in cur.fetchall()]

        return order
    finally:
        conn.close()

def get_recent_orders_by_user(user_id: int, days: int = 7) -> List[Dict[str, Any]]:
    """Retorna os pedidos enviados por um setor nos últimos X dias."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")

        cur.execute("""
            SELECT p.id, p.usuario_id, p.data_hora, p.status, p.observacoes,
                   u.nome_setor, u.icone as icone_setor
            FROM pedidos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.usuario_id = ? AND p.data_hora >= ? AND p.status != 'Rascunho'
            ORDER BY p.data_hora DESC
        """, (user_id, cutoff_date))

        pedidos_rows = cur.fetchall()
        result = []
        for row in pedidos_rows:
            order = dict(row)
            pid = order["id"]

            cur.execute("""
                SELECT ip.id, ip.produto_id, ip.quantidade_pedida,
                       prod.nome as nome_produto, prod.unidade_medida
                FROM itens_pedido ip
                JOIN produtos prod ON prod.id = ip.produto_id
                WHERE ip.pedido_id = ?
            """, (pid,))
            order["itens_catalogo"] = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT id, descricao_item, quantidade, unidade_medida
                FROM itens_avulsos
                WHERE pedido_id = ?
            """, (pid,))
            order["itens_avulsos"] = [dict(r) for r in cur.fetchall()]

            result.append(order)
        return result
    finally:
        conn.close()

def get_orders_by_date(date_str: str, setor: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    date_str no formato 'YYYY-MM-DD'.
    Retorna todos os pedidos daquela data (para o painel da administração).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        start = f"{date_str} 00:00:00"
        end = f"{date_str} 23:59:59"

        query = """
            SELECT p.id, p.usuario_id, p.data_hora, p.status, p.observacoes,
                   u.nome_setor, u.icone as icone_setor
            FROM pedidos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ?
        """
        params = [start, end]

        if setor and setor != "todos":
            query += " AND LOWER(u.nome_setor) = LOWER(?)"
            params.append(setor)

        if status and status != "todos":
            query += " AND p.status = ?"
            params.append(status)
        else:
            query += " AND p.status IN ('Pendente', 'Aprovado')"

        query += " ORDER BY p.data_hora DESC, p.id DESC"

        cur.execute(query, params)
        orders = []
        for r in cur.fetchall():
            order = dict(r)
            pid = order["id"]

            cur.execute("""
                SELECT ip.id, ip.produto_id, ip.quantidade_pedida,
                       prod.nome as nome_produto, prod.unidade_medida, prod.categoria
                FROM itens_pedido ip
                JOIN produtos prod ON prod.id = ip.produto_id
                WHERE ip.pedido_id = ?
                ORDER BY prod.nome ASC
            """, (pid,))
            order["itens_catalogo"] = [dict(it) for it in cur.fetchall()]

            cur.execute("""
                SELECT id, descricao_item, quantidade, unidade_medida
                FROM itens_avulsos
                WHERE pedido_id = ?
                ORDER BY id ASC
            """, (pid,))
            order["itens_avulsos"] = [dict(it) for it in cur.fetchall()]

            orders.append(order)
        return orders
    finally:
        conn.close()

def get_completed_orders(
    date_str: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    setor: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retorna os pedidos concluídos (status = 'Comprado') para a Aba 5 (Pedidos Concluídos).
    Filtra por data específica, intervalo de datas (start_date/end_date), ou últimos 30 dias por padrão.
    Opcionalmente filtra por praça/setor.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT p.id, p.id AS pedido_id, p.usuario_id, p.data_hora, p.status, p.observacoes,
                   u.nome_setor, u.nome_setor AS praca, u.icone as icone_setor
            FROM pedidos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.status = 'Comprado'
        """
        params: List[Any] = []

        if date_str and str(date_str).lower() not in ("todos", "all", ""):
            query += " AND (DATE(p.data_hora) = ? OR p.data_hora BETWEEN ? AND ?)"
            params.extend([date_str, f"{date_str} 00:00:00", f"{date_str} 23:59:59"])
        elif start_date and end_date:
            query += " AND p.data_hora BETWEEN ? AND ?"
            params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
        elif start_date:
            query += " AND p.data_hora >= ?"
            params.append(f"{start_date} 00:00:00")
        elif end_date:
            query += " AND p.data_hora <= ?"
            params.append(f"{end_date} 23:59:59")

        if setor and setor.lower() != "todos":
            query += " AND LOWER(u.nome_setor) = LOWER(?)"
            params.append(setor)

        query += " ORDER BY p.data_hora DESC, p.id DESC"

        cur.execute(query, params)
        orders = []
        for r in cur.fetchall():
            order = dict(r)
            pid = order["id"]

            cur.execute("""
                SELECT ip.id, ip.produto_id, ip.quantidade_pedida,
                       prod.nome as nome_produto, prod.unidade_medida, prod.categoria
                FROM itens_pedido ip
                JOIN produtos prod ON prod.id = ip.produto_id
                WHERE ip.pedido_id = ?
                ORDER BY prod.nome ASC
            """, (pid,))
            order["itens_catalogo"] = [dict(it) for it in cur.fetchall()]

            cur.execute("""
                SELECT id, descricao_item, quantidade, unidade_medida
                FROM itens_avulsos
                WHERE pedido_id = ?
                ORDER BY id ASC
            """, (pid,))
            order["itens_avulsos"] = [dict(it) for it in cur.fetchall()]

            orders.append(order)
        return orders
    finally:
        conn.close()

# --- CONSOLIDAÇÃO DE COMPRAS (ORDEM UNIFICADA) ---

def get_consolidated_orders(date_str: str, status_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Agrupamento SQL unificado para cotação com fornecedores.
    Soma as quantidades pedidas por produto de todos os setores na data especificada.
    Considera exclusivamente pedidos ativos (Pendente, Aprovado), excluindo Rascunhos e Comprados.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        start = f"{date_str} 00:00:00"
        end = f"{date_str} 23:59:59"

        # 1. Itens de Catálogo Consolidados
        query_catalogo = """
            SELECT 
                prod.id as produto_id,
                prod.nome as produto_nome,
                prod.unidade_medida,
                prod.categoria,
                SUM(ip.quantidade_pedida) as quantidade_total,
                GROUP_CONCAT(DISTINCT u.nome_setor) as setores_solicitantes,
                COUNT(DISTINCT p.id) as total_pedidos_item
            FROM itens_pedido ip
            JOIN pedidos p ON p.id = ip.pedido_id
            JOIN produtos prod ON prod.id = ip.produto_id
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ?
        """
        params_cat = [start, end]
        if status_filter and status_filter != "todos":
            query_catalogo += " AND p.status = ?"
            params_cat.append(status_filter)
        else:
            query_catalogo += " AND p.status IN ('Pendente', 'Aprovado')"

        query_catalogo += """
            GROUP BY prod.id, prod.nome, prod.unidade_medida, prod.categoria
            ORDER BY prod.categoria ASC, prod.nome ASC
        """
        cur.execute(query_catalogo, params_cat)
        catalogo_consolidado = [dict(r) for r in cur.fetchall()]

        # 2. Itens Avulsos Consolidados
        query_avulsos = """
            SELECT 
                ia.descricao_item,
                ia.unidade_medida,
                SUM(ia.quantidade) as quantidade_total,
                GROUP_CONCAT(DISTINCT u.nome_setor) as setores_solicitantes,
                COUNT(DISTINCT p.id) as total_pedidos_item,
                GROUP_CONCAT(DISTINCT p.observacoes) as notas_relevantes
            FROM itens_avulsos ia
            JOIN pedidos p ON p.id = ia.pedido_id
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ?
        """
        params_av = [start, end]
        if status_filter and status_filter != "todos":
            query_avulsos += " AND p.status = ?"
            params_av.append(status_filter)
        else:
            query_avulsos += " AND p.status IN ('Pendente', 'Aprovado')"

        query_avulsos += """
            GROUP BY LOWER(TRIM(ia.descricao_item)), LOWER(TRIM(ia.unidade_medida))
            ORDER BY ia.descricao_item ASC
        """
        cur.execute(query_avulsos, params_av)
        avulsos_consolidados = [dict(r) for r in cur.fetchall()]

        # 3. Estatísticas do Dia
        cur.execute("""
            SELECT 
                COUNT(*) as total_pedidos,
                SUM(CASE WHEN status = 'Pendente' THEN 1 ELSE 0 END) as total_pendentes,
                SUM(CASE WHEN status = 'Aprovado' THEN 1 ELSE 0 END) as total_aprovados,
                SUM(CASE WHEN status = 'Comprado' THEN 1 ELSE 0 END) as total_comprados,
                COUNT(DISTINCT usuario_id) as total_setores_ativos
            FROM pedidos
            WHERE data_hora BETWEEN ? AND ? AND status != 'Rascunho'
        """, (start, end))
        stats = dict(cur.fetchone())

        return {
            "data": date_str,
            "catalogo": catalogo_consolidado,
            "avulsos": avulsos_consolidados,
            "resumo": stats
        }
    finally:
        conn.close()

# --- RELATÓRIOS E INDICADORES ANALÍTICOS (DASHBOARD) ---

def get_analytics_data(
    period_type: str = "month",
    year: Optional[int] = None,
    month: Optional[int] = None,
    sector: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula indicadores agregados (quantidade, soma, médias), distribuição por praça
    e o Ranking Top 10 de produtos mais solicitados no período especificado.
    period_type: 'month', 'semester_1', 'semester_2', 'year'
    """
    import calendar
    now = datetime.now()
    year = int(year) if year else now.year
    month = int(month) if month else now.month

    meses_pt = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]

    # Determina o intervalo de datas
    if period_type in ("semester_1", "semester1"):
        period_type = "semester_1"
        start = f"{year:04d}-01-01 00:00:00"
        end = f"{year:04d}-06-30 23:59:59"
        period_label = f"1º Semestre de {year} (Janeiro a Junho)"
    elif period_type in ("semester_2", "semester2"):
        period_type = "semester_2"
        start = f"{year:04d}-07-01 00:00:00"
        end = f"{year:04d}-12-31 23:59:59"
        period_label = f"2º Semestre de {year} (Julho a Dezembro)"
    elif period_type == "year":
        period_type = "year"
        start = f"{year:04d}-01-01 00:00:00"
        end = f"{year:04d}-12-31 23:59:59"
        period_label = f"Ano Completo de {year}"
    else:  # default 'month'
        period_type = "month"
        last_day = calendar.monthrange(year, month)[1]
        start = f"{year:04d}-{month:02d}-01 00:00:00"
        end = f"{year:04d}-{month:02d}-{last_day:02d} 23:59:59"
        period_label = f"{meses_pt[month - 1]} de {year}"

    conn = get_connection()
    try:
        cur = conn.cursor()
        sector_filter_sql = ""
        sector_params = []
        if sector and sector.lower() != "todos":
            sector_filter_sql = " AND LOWER(u.nome_setor) = LOWER(?)"
            sector_params = [sector]

        # 1. Contagem geral de pedidos e status
        query_stats = f"""
            SELECT 
                COUNT(DISTINCT p.id) as total_pedidos,
                COUNT(DISTINCT DATE(p.data_hora)) as dias_ativos,
                SUM(CASE WHEN p.status = 'Pendente' THEN 1 ELSE 0 END) as pedidos_pendentes,
                SUM(CASE WHEN p.status = 'Aprovado' THEN 1 ELSE 0 END) as pedidos_aprovados,
                SUM(CASE WHEN p.status = 'Comprado' THEN 1 ELSE 0 END) as pedidos_comprados
            FROM pedidos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho' {sector_filter_sql}
        """
        cur.execute(query_stats, [start, end] + sector_params)
        stats_row = dict(cur.fetchone() or {})
        total_pedidos = stats_row.get("total_pedidos") or 0
        dias_ativos = stats_row.get("dias_ativos") or 0
        pedidos_pendentes = stats_row.get("pedidos_pendentes") or 0
        pedidos_aprovados = stats_row.get("pedidos_aprovados") or 0
        pedidos_comprados = stats_row.get("pedidos_comprados") or 0

        # 2. Volumes somados: Catálogo
        query_cat_vol = f"""
            SELECT 
                COALESCE(SUM(ip.quantidade_pedida), 0) as soma_catalogo,
                COUNT(ip.id) as linhas_catalogo
            FROM itens_pedido ip
            JOIN pedidos p ON p.id = ip.pedido_id
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho' {sector_filter_sql}
        """
        cur.execute(query_cat_vol, [start, end] + sector_params)
        cat_vol = dict(cur.fetchone() or {})
        soma_catalogo = float(cat_vol.get("soma_catalogo") or 0)
        linhas_catalogo = cat_vol.get("linhas_catalogo") or 0

        # 3. Volumes somados: Avulsos
        query_av_vol = f"""
            SELECT 
                COALESCE(SUM(ia.quantidade), 0) as soma_avulsos,
                COUNT(ia.id) as linhas_avulsos
            FROM itens_avulsos ia
            JOIN pedidos p ON p.id = ia.pedido_id
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho' {sector_filter_sql}
        """
        cur.execute(query_av_vol, [start, end] + sector_params)
        av_vol = dict(cur.fetchone() or {})
        soma_avulsos = float(av_vol.get("soma_avulsos") or 0)
        linhas_avulsos = av_vol.get("linhas_avulsos") or 0

        soma_total_itens = round(soma_catalogo + soma_avulsos, 2)
        media_itens_por_pedido = round(soma_total_itens / total_pedidos, 1) if total_pedidos > 0 else 0.0
        media_pedidos_por_dia = round(total_pedidos / dias_ativos, 1) if dias_ativos > 0 else 0.0
        taxa_atendimento = round(((pedidos_aprovados + pedidos_comprados) / total_pedidos) * 100, 1) if total_pedidos > 0 else 0.0

        # 4. TOP 10 PRODUTOS MAIS PEDIDOS (Catálogo)
        query_top10 = f"""
            SELECT 
                prod.id as produto_id,
                prod.nome as produto_nome,
                prod.categoria,
                prod.unidade_medida,
                prod.setor_responsavel,
                ROUND(SUM(ip.quantidade_pedida), 2) as total_quantidade,
                COUNT(DISTINCT p.id) as frequencia_pedidos,
                GROUP_CONCAT(DISTINCT u.nome_setor) as setores_solicitantes
            FROM itens_pedido ip
            JOIN pedidos p ON p.id = ip.pedido_id
            JOIN produtos prod ON prod.id = ip.produto_id
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho' {sector_filter_sql}
            GROUP BY prod.id, prod.nome, prod.categoria, prod.unidade_medida, prod.setor_responsavel
            ORDER BY total_quantidade DESC, frequencia_pedidos DESC
            LIMIT 10
        """
        cur.execute(query_top10, [start, end] + sector_params)
        top10_rows = [dict(r) for r in cur.fetchall()]

        max_qty = top10_rows[0]["total_quantidade"] if top10_rows else 0
        for idx, item in enumerate(top10_rows, 1):
            item["posicao"] = idx
            item["percentual_max"] = round((item["total_quantidade"] / max_qty) * 100, 1) if max_qty > 0 else 0
            item["setores_list"] = [s.strip() for s in (item["setores_solicitantes"] or "").split(",") if s.strip()]

        # 5. Distribuição por Praça (Setor)
        query_setores = """
            SELECT 
                u.nome_setor,
                u.icone as icone_setor,
                COUNT(DISTINCT p.id) as total_pedidos,
                ROUND(COALESCE(SUM(ip.quantidade_pedida), 0), 1) as total_volume
            FROM usuarios u
            LEFT JOIN pedidos p ON p.usuario_id = u.id AND p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho'
            LEFT JOIN itens_pedido ip ON ip.pedido_id = p.id
            WHERE u.nivel_acesso = 'operador'
            GROUP BY u.id, u.nome_setor, u.icone
            ORDER BY total_pedidos DESC, total_volume DESC
        """
        cur.execute(query_setores, (start, end))
        distribuicao_setores = []
        for r in cur.fetchall():
            d = dict(r)
            d["percentual_pedidos"] = round((d["total_pedidos"] / total_pedidos) * 100, 1) if total_pedidos > 0 else 0.0
            distribuicao_setores.append(d)

        # 6. Top 5 Itens Avulsos (Fora de Catálogo)
        query_top_avulsos = f"""
            SELECT 
                ia.descricao_item,
                ia.unidade_medida,
                ROUND(SUM(ia.quantidade), 2) as total_quantidade,
                COUNT(DISTINCT p.id) as frequencia_pedidos,
                GROUP_CONCAT(DISTINCT u.nome_setor) as setores_solicitantes
            FROM itens_avulsos ia
            JOIN pedidos p ON p.id = ia.pedido_id
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho' {sector_filter_sql}
            GROUP BY LOWER(TRIM(ia.descricao_item)), LOWER(TRIM(ia.unidade_medida))
            ORDER BY total_quantidade DESC, frequencia_pedidos DESC
            LIMIT 5
        """
        cur.execute(query_top_avulsos, [start, end] + sector_params)
        top_avulsos = [dict(r) for r in cur.fetchall()]

        # 7. Timeline / Evolução temporal
        if period_type == "month":
            query_timeline = f"""
                SELECT 
                    DATE(p.data_hora) as data_chave,
                    COUNT(DISTINCT p.id) as total_pedidos,
                    ROUND(COALESCE(SUM(ip.quantidade_pedida), 0), 1) as total_volume
                FROM pedidos p
                JOIN usuarios u ON u.id = p.usuario_id
                LEFT JOIN itens_pedido ip ON ip.pedido_id = p.id
                WHERE p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho' {sector_filter_sql}
                GROUP BY DATE(p.data_hora)
                ORDER BY data_chave ASC
            """
        else:
            query_timeline = f"""
                SELECT 
                    strftime('%Y-%m', p.data_hora) as data_chave,
                    COUNT(DISTINCT p.id) as total_pedidos,
                    ROUND(COALESCE(SUM(ip.quantidade_pedida), 0), 1) as total_volume
                FROM pedidos p
                JOIN usuarios u ON u.id = p.usuario_id
                LEFT JOIN itens_pedido ip ON ip.pedido_id = p.id
                WHERE p.data_hora BETWEEN ? AND ? AND p.status != 'Rascunho' {sector_filter_sql}
                GROUP BY strftime('%Y-%m', p.data_hora)
                ORDER BY data_chave ASC
            """
        cur.execute(query_timeline, [start, end] + sector_params)
        timeline = [dict(r) for r in cur.fetchall()]

        return {
            "periodo": {
                "tipo": period_type,
                "ano": year,
                "mes": month,
                "label": period_label,
                "inicio": start,
                "fim": end,
                "setor_filtro": sector or "todos"
            },
            "kpis": {
                "total_pedidos": total_pedidos,
                "soma_total_itens": soma_total_itens,
                "soma_catalogo": round(soma_catalogo, 2),
                "soma_avulsos": round(soma_avulsos, 2),
                "media_itens_por_pedido": media_itens_por_pedido,
                "dias_ativos": dias_ativos,
                "media_pedidos_por_dia": media_pedidos_por_dia,
                "taxa_atendimento": taxa_atendimento,
                "pedidos_pendentes": pedidos_pendentes,
                "pedidos_aprovados": pedidos_aprovados,
                "pedidos_comprados": pedidos_comprados
            },
            "top10_produtos": top10_rows,
            "distribuicao_setores": distribuicao_setores,
            "top_avulsos": top_avulsos,
            "timeline": timeline
        }
    finally:
        conn.close()
