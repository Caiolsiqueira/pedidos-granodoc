import os
import unittest
import tempfile
import json
from datetime import datetime

# Configura banco temporário para testes isolados
test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db_path = test_db_file.name
test_db_file.close()
os.environ["GRANODOC_DB_PATH"] = test_db_path

import database
import auth
import pdf_generator
import template_generator

class TestPedidosGranodoc(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Inicializa o banco de testes
        database.init_db(test_db_path)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

    def test_01_users_seed(self):
        """Verifica se os 5 usuários e setores foram criados corretamente."""
        users = database.get_all_users()
        self.assertEqual(len(users), 5)
        setores = [u["nome_setor"] for u in users]
        self.assertIn("Pizza", setores)
        self.assertIn("Cozinha", setores)
        self.assertIn("Bar", setores)
        self.assertIn("Salão", setores)
        self.assertIn("Administracao", setores)

    def test_02_products_seed(self):
        """Verifica se os produtos de catálogo foram criados para os 4 setores operacionais."""
        for setor in ["Pizza", "Cozinha", "Bar", "Salão"]:
            prods = database.get_products(setor=setor)
            self.assertGreaterEqual(len(prods), 8, f"Setor {setor} deve ter ao menos 8 produtos.")

    def test_03_authentication_pins(self):
        """Verifica a validação de PINs corretos e rejeição de PINs incorretos."""
        # PINs válidos
        self.assertIsNotNone(database.authenticate_user("Pizza", "1001"))
        self.assertIsNotNone(database.authenticate_user("Cozinha", "1002"))
        self.assertIsNotNone(database.authenticate_user("Bar", "1003"))
        self.assertIsNotNone(database.authenticate_user("Salão", "1004"))
        self.assertIsNotNone(database.authenticate_user("Administracao", "9999"))

        # Autenticação direta pelo PIN
        user_pizza = database.authenticate_by_pin_only("1001")
        self.assertIsNotNone(user_pizza)
        self.assertEqual(user_pizza["nome_setor"], "Pizza")

        user_admin = database.authenticate_by_pin_only("9999")
        self.assertIsNotNone(user_admin)
        self.assertEqual(user_admin["nivel_acesso"], "admin")

        # PIN incorreto
        self.assertIsNone(database.authenticate_user("Pizza", "9999"))
        self.assertIsNone(database.authenticate_by_pin_only("0000"))

    def test_04_create_order_and_history(self):
        """Testa o fluxo de criação de pedido com itens de catálogo e avulsos."""
        user_pizza = database.get_user_by_sector("Pizza")
        pizza_prods = database.get_products(setor="Pizza")
        prod1 = pizza_prods[0]
        prod2 = pizza_prods[1]

        itens_cat = [
            {"produto_id": prod1["id"], "quantidade": 2.0},
            {"produto_id": prod2["id"], "quantidade": 5.0},
        ]
        itens_av = [
            {"descricao": "Manjericão Roxo Fresco", "quantidade": 3.0, "unidade_medida": "pct"}
        ]

        pedido_id = database.create_order(
            usuario_id=user_pizza["id"],
            itens_catalogo=itens_cat,
            itens_avulsos=itens_av,
            observacoes="Entregar antes das 17h para o pré-preparo."
        )
        self.assertIsInstance(pedido_id, int)
        self.assertGreater(pedido_id, 0)

        # Consulta detalhes do pedido
        detalhes = database.get_order_details(pedido_id)
        self.assertEqual(detalhes["status"], "Pendente")
        self.assertEqual(detalhes["nome_setor"], "Pizza")
        self.assertEqual(len(detalhes["itens_catalogo"]), 2)
        self.assertEqual(len(detalhes["itens_avulsos"]), 1)
        self.assertEqual(detalhes["observacoes"], "Entregar antes das 17h para o pré-preparo.")

        # Consulta histórico dos últimos 7 dias
        recentes = database.get_recent_orders_by_user(user_pizza["id"], days=7)
        self.assertTrue(any(p["id"] == pedido_id for p in recentes))

    def test_05_update_order_status(self):
        """Testa a esteira de transição de status: Pendente -> Aprovado -> Comprado."""
        user_bar = database.get_user_by_sector("Bar")
        bar_prods = database.get_products(setor="Bar")
        pedido_id = database.create_order(
            usuario_id=user_bar["id"],
            itens_catalogo=[{"produto_id": bar_prods[0]["id"], "quantidade": 4.0}],
            itens_avulsos=[],
            observacoes="Urgente para o fim de semana"
        )

        detalhes = database.get_order_details(pedido_id)
        self.assertEqual(detalhes["status"], "Pendente")

        # Atualiza para Aprovado
        ok = database.update_order_status(pedido_id, "Aprovado")
        self.assertTrue(ok)
        detalhes = database.get_order_details(pedido_id)
        self.assertEqual(detalhes["status"], "Aprovado")

        # Atualiza para Comprado
        ok = database.update_order_status(pedido_id, "Comprado")
        self.assertTrue(ok)
        detalhes = database.get_order_details(pedido_id)
        self.assertEqual(detalhes["status"], "Comprado")

    def test_06_sql_consolidation(self):
        """Testa a consolidação unificada em SQL para pedidos da mesma data."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        user_cozinha = database.get_user_by_sector("Cozinha")
        user_salao = database.get_user_by_sector("Salão")

        coz_prods = database.get_products(setor="Cozinha")
        salao_prods = database.get_products(setor="Salão")

        # Cria pedido da Cozinha
        database.create_order(
            usuario_id=user_cozinha["id"],
            itens_catalogo=[{"produto_id": coz_prods[0]["id"], "quantidade": 10.0}],
            itens_avulsos=[{"descricao": "Trufas Negras", "quantidade": 1.0, "unidade_medida": "pct"}]
        )

        # Cria pedido do Salão
        database.create_order(
            usuario_id=user_salao["id"],
            itens_catalogo=[{"produto_id": salao_prods[0]["id"], "quantidade": 12.0}],
            itens_avulsos=[]
        )

        consolidado = database.get_consolidated_orders(hoje)
        self.assertIn("catalogo", consolidado)
        self.assertIn("avulsos", consolidado)
        self.assertIn("resumo", consolidado)

        # Verifica se há itens no catálogo consolidado
        self.assertGreater(len(consolidado["catalogo"]), 0)
        # Verifica se há itens avulsos consolidados
        self.assertGreater(len(consolidado["avulsos"]), 0)

        # Verifica as estatísticas do resumo
        self.assertGreaterEqual(consolidado["resumo"]["total_pedidos"], 3)
        self.assertGreaterEqual(consolidado["resumo"]["total_setores_ativos"], 2)

    def test_07_pdf_generation(self):
        """Verifica a geração do relatório em PDF da ordem de compras consolidada."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        consolidado = database.get_consolidated_orders(hoje)
        pdf_stream = pdf_generator.generate_consolidated_pdf(consolidado)
        self.assertIsNotNone(pdf_stream)
        pdf_bytes = pdf_stream.read()
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_08_categories_crud(self):
        """Testa criação, listagem e exclusão de categorias para um setor."""
        # Cria nova categoria na Pizza
        cat_id = database.create_category("Farinhas Especiais", "Pizza")
        self.assertIsNotNone(cat_id)
        self.assertGreater(cat_id, 0)

        # Listagem
        cats = database.get_categories_by_sector("Pizza")
        nomes = [c["nome"] for c in cats]
        self.assertIn("Farinhas Especiais", nomes)

        # Deletar categoria
        ok = database.delete_category(cat_id)
        self.assertTrue(ok)
        cats_after = database.get_categories_by_sector("Pizza")
        self.assertNotIn("Farinhas Especiais", [c["nome"] for c in cats_after])

    def test_09_product_crud_and_batch(self):
        """Testa criação individual, edição, inserção em lote e exclusão segura."""
        # Criação individual
        prod_id = database.create_product("Azeite Trufado", "Pizza", "un", "Temperos")
        self.assertIsNotNone(prod_id)

        # Edição
        ok = database.update_product(prod_id, "Azeite Trufado Extra", "Pizza", "frasco", "Temperos")
        self.assertTrue(ok)
        prods = database.get_products(setor="Pizza")
        prod = next(p for p in prods if p["id"] == prod_id)
        self.assertEqual(prod["nome"], "Azeite Trufado Extra")
        self.assertEqual(prod["unidade_medida"], "frasco")

        # Exclusão direta (sem pedidos vinculados -> delete definitivo)
        deleted = database.delete_product(prod_id)
        self.assertTrue(deleted["success"])
        self.assertEqual(deleted["action"], "deleted")
        prods_after = database.get_products(setor="Pizza")
        self.assertFalse(any(p["id"] == prod_id for p in prods_after))

        # Cadastro em lote (Batch)
        lote = [
            {"nome": "Farinha Manitoba", "setor": "Pizza", "unidade_medida": "kg", "categoria": "Farinhas"},
            {"nome": "Semolina de Grão Duro", "setor": "Pizza", "unidade_medida": "kg", "categoria": "Farinhas"},
            {"nome": "Fermento Seco Especial", "setor": "Pizza", "unidade_medida": "pct", "categoria": "Fermentos"}
        ]
        created = database.create_products_batch(lote)
        self.assertEqual(created["count"], 3)

        # Verifica se produtos do lote foram inseridos
        prods_lote = database.get_products(setor="Pizza")
        nomes_lote = [p["nome"] for p in prods_lote]
        self.assertIn("Farinha Manitoba", nomes_lote)
        self.assertIn("Semolina de Grão Duro", nomes_lote)
        self.assertIn("Fermento Seco Especial", nomes_lote)

    def test_10_multi_sector_product(self):
        """Testa produtos compartilhados entre múltiplas praças (multi-setor)."""
        # 1. Cria produto compartilhado entre Pizza e Cozinha
        provolone_id = database.create_product(
            nome="Queijo Provolone Defumado",
            setor=["Pizza", "Cozinha"],
            unidade="kg",
            categoria="Queijos"
        )
        self.assertIsNotNone(provolone_id)

        # 2. Verifica se Pizza enxerga o produto
        pizza_prods = database.get_products(setor="Pizza")
        self.assertTrue(any(p["id"] == provolone_id for p in pizza_prods))

        # 3. Verifica se Cozinha enxerga o produto
        coz_prods = database.get_products(setor="Cozinha")
        self.assertTrue(any(p["id"] == provolone_id for p in coz_prods))

        # 4. Verifica se Bar NÃO enxerga o produto
        bar_prods = database.get_products(setor="Bar")
        self.assertFalse(any(p["id"] == provolone_id for p in bar_prods))

        # 5. Verifica setores no get_product_by_id
        prod_data = database.get_product_by_id(provolone_id)
        self.assertIn("Pizza", prod_data["setores"])
        self.assertIn("Cozinha", prod_data["setores"])

        # 6. Atualiza praças para Bar e Salão
        updated = database.update_product(
            prod_id=provolone_id,
            nome="Gelo Cristalino Esferas",
            setor=["Bar", "Salão"],
            unidade="pct",
            categoria="Gelo & Bases"
        )
        self.assertTrue(updated)

        # 7. Verifica nova distribuição de praças
        bar_prods_after = database.get_products(setor="Bar")
        self.assertTrue(any(p["id"] == provolone_id for p in bar_prods_after))

        salao_prods_after = database.get_products(setor="Salão")
        self.assertTrue(any(p["id"] == provolone_id for p in salao_prods_after))

        pizza_prods_after = database.get_products(setor="Pizza")
        self.assertFalse(any(p["id"] == provolone_id for p in pizza_prods_after))

        # 8. Limpeza
        database.delete_product(provolone_id)

    def test_11_analytics_queries(self):
        """Testa o motor de BI & Estatísticas (get_analytics_data) para diferentes períodos e filtros."""
        now = datetime.now()
        cur_year = now.year
        cur_month = now.month

        # 1. Análise no mês atual (onde foram criados pedidos nos testes anteriores)
        data_mes = database.get_analytics_data(period_type="month", year=cur_year, month=cur_month)
        self.assertIn("kpis", data_mes)
        self.assertIn("top10_produtos", data_mes)
        self.assertIn("distribuicao_setores", data_mes)
        self.assertIn("top_avulsos", data_mes)
        self.assertIn("timeline", data_mes)
        self.assertIn("periodo", data_mes)

        kpis = data_mes["kpis"]
        self.assertGreaterEqual(kpis["total_pedidos"], 1)
        self.assertGreaterEqual(kpis["soma_total_itens"], 1.0)
        self.assertGreater(kpis["media_itens_por_pedido"], 0.0)

        # Verifica ranking top 10
        top10 = data_mes["top10_produtos"]
        self.assertIsInstance(top10, list)
        self.assertLessEqual(len(top10), 10)
        if len(top10) > 0:
            p1 = top10[0]
            self.assertEqual(p1["posicao"], 1)
            self.assertEqual(p1["percentual_max"], 100.0)
            self.assertIn("produto_nome", p1)
            self.assertIn("total_quantidade", p1)

        # 2. Teste do 1º Semestre
        data_sem1 = database.get_analytics_data(period_type="semester_1", year=cur_year)
        self.assertEqual(data_sem1["periodo"]["tipo"], "semester_1")
        self.assertIn(f"1º Semestre de {cur_year}", data_sem1["periodo"]["label"])

        # 3. Teste do 2º Semestre
        data_sem2 = database.get_analytics_data(period_type="semester_2", year=cur_year)
        self.assertEqual(data_sem2["periodo"]["tipo"], "semester_2")
        self.assertIn(f"2º Semestre de {cur_year}", data_sem2["periodo"]["label"])

        # 4. Teste do Ano Inteiro
        data_ano = database.get_analytics_data(period_type="year", year=cur_year)
        self.assertEqual(data_ano["periodo"]["tipo"], "year")
        self.assertIn(f"Ano Completo de {cur_year}", data_ano["periodo"]["label"])
        self.assertGreaterEqual(data_ano["kpis"]["total_pedidos"], kpis["total_pedidos"])

        # 5. Teste com filtro por praça específica
        data_pizza = database.get_analytics_data(period_type="year", year=cur_year, sector="Pizza")
        self.assertEqual(data_pizza["periodo"]["setor_filtro"], "Pizza")
        self.assertGreaterEqual(data_pizza["kpis"]["total_pedidos"], 1)

        # 6. Teste com período sem movimentação (ano 2020)
        data_vazio = database.get_analytics_data(period_type="year", year=2020)
        self.assertEqual(data_vazio["kpis"]["total_pedidos"], 0)
        self.assertEqual(data_vazio["kpis"]["soma_total_itens"], 0.0)
        self.assertEqual(data_vazio["kpis"]["media_itens_por_pedido"], 0.0)
        self.assertEqual(len(data_vazio["top10_produtos"]), 0)

    def test_12_template_generator_and_parsing(self):
        """Testa geração dos modelos Excel (.xlsx) e CSV (.csv), e o parser de arquivos."""
        # 1. Geração de bytes Excel
        xlsx_bytes = template_generator.generate_excel_bytes()
        self.assertIsInstance(xlsx_bytes, bytes)
        self.assertGreater(len(xlsx_bytes), 1000)
        # Cabeçalho ZIP de arquivo .xlsx (PK..)
        self.assertTrue(xlsx_bytes.startswith(b"PK\x03\x04"))

        # 2. Geração de bytes CSV
        csv_bytes = template_generator.generate_csv_bytes()
        self.assertIsInstance(csv_bytes, bytes)
        self.assertGreater(len(csv_bytes), 200)
        # BOM UTF-8
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))

        # 3. Parser de arquivo Excel gerado
        parsed_from_excel = template_generator.parse_uploaded_file(
            file_bytes=xlsx_bytes,
            filename="teste.xlsx",
            default_setor="Pizza"
        )
        self.assertGreaterEqual(len(parsed_from_excel), 8)
        first_item = parsed_from_excel[0]
        self.assertIn("nome", first_item)
        self.assertIn("categoria", first_item)
        self.assertIn("unidade", first_item)
        self.assertIn("setor", first_item)
        self.assertEqual(first_item["nome"], "Farinha de Trigo Especial 00")
        self.assertEqual(first_item["unidade"], "kg")

        # 4. Parser de arquivo CSV gerado
        parsed_from_csv = template_generator.parse_uploaded_file(
            file_bytes=csv_bytes,
            filename="teste.csv",
            default_setor="Pizza"
        )
        self.assertGreaterEqual(len(parsed_from_csv), 8)
        self.assertEqual(parsed_from_csv[0]["nome"], "Farinha de Trigo Especial 00")

        # 5. Cadastro em lote dos itens parseados no banco de dados
        res = database.create_products_batch(parsed_from_excel[:3])
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["count"], 1)

    def test_13_batch_delete_products(self):
        """Testa a exclusão em lote mantendo integridade referencial."""
        # 1. Cria 3 produtos sem pedidos vinculados
        id1 = database.create_product("Item Teste Lote 1", "Pizza", "kg", "Geral")
        id2 = database.create_product("Item Teste Lote 2", "Cozinha", "un", "Geral")
        id3 = database.create_product("Item Teste Lote 3", "Bar", "litro", "Bebidas")

        # 2. Cria 1 produto com pedido vinculado (deve ser desativado, ativo=0)
        id_with_order = database.create_product("Item Com Pedido Lote", "Salão", "un", "Vinhos")
        user_salao = database.get_user_by_sector("Salão")
        database.create_order(
            usuario_id=user_salao["id"],
            itens_catalogo=[{"produto_id": id_with_order, "quantidade": 10.0}],
            itens_avulsos=[]
        )

        # 3. Executa exclusão em lote dos 4 produtos
        batch_ids = [id1, id2, id3, id_with_order]
        res = database.delete_products_batch(batch_ids)

        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 4)
        self.assertEqual(res["deleted"], 3)
        self.assertEqual(res["deactivated"], 1)

        # Verifica se os 3 produtos sem pedido foram excluídos permanentemente
        self.assertIsNone(database.get_product_by_id(id1))
        self.assertIsNone(database.get_product_by_id(id2))
        self.assertIsNone(database.get_product_by_id(id3))

        # Verifica se o produto com pedido histórico foi desativado (ativo=0)
        prod_archived = database.get_product_by_id(id_with_order)
        self.assertIsNotNone(prod_archived)
        self.assertEqual(prod_archived["ativo"], 0)

        # 4. Teste com lista vazia
        res_empty = database.delete_products_batch([])
        self.assertTrue(res_empty["success"])
        self.assertEqual(res_empty["count"], 0)

    def test_14_order_draft_lifecycle(self):
        """Testa o ciclo de vida completo de Rascunho (Draft): salvar, atualizar, isolamento e envio."""
        user_bar = database.get_user_by_sector("Bar")
        prods_bar = database.get_products(setor="Bar")
        p1 = prods_bar[0]
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. Salvar rascunho inicial
        draft_id1 = database.save_order_draft(
            usuario_id=user_bar["id"],
            itens_catalogo=[{"produto_id": p1["id"], "quantidade": 5.0}],
            itens_avulsos=[{"descricao": "Canudos de Vidro", "quantidade": 20.0, "unidade_medida": "un"}],
            observacoes="Rascunho inicial Bar"
        )
        self.assertIsInstance(draft_id1, int)

        # 2. Consultar rascunho ativo
        draft_data = database.get_draft_by_sector(user_bar["id"])
        self.assertIsNotNone(draft_data)
        self.assertEqual(draft_data["id"], draft_id1)
        self.assertEqual(draft_data["status"], "Rascunho")
        self.assertEqual(len(draft_data["itens_catalogo"]), 1)
        self.assertEqual(draft_data["itens_catalogo"][0]["quantidade_pedida"], 5.0)
        self.assertEqual(len(draft_data["itens_avulsos"]), 1)

        # 3. Visibilidade Estrita: NÃO pode aparecer na visão diária da Administração
        admin_orders = database.get_orders_by_date(today)
        self.assertFalse(any(o["id"] == draft_id1 for o in admin_orders))

        # 4. Visibilidade Estrita: NÃO pode ser consolidado
        consolidated = database.get_consolidated_orders(today)
        prods_in_cat = [c["produto_id"] for c in consolidated["catalogo"]]
        # O item avulso "Canudos de Vidro" não deve estar na consolidação
        avulsos_descs = [a["descricao_item"] for a in consolidated["avulsos"]]
        self.assertNotIn("Canudos de Vidro", avulsos_descs)

        # 5. Salvar novamente no mesmo dia: DEVE atualizar o mesmo registro (máximo 1 rascunho/dia)
        draft_id2 = database.save_order_draft(
            usuario_id=user_bar["id"],
            itens_catalogo=[{"produto_id": p1["id"], "quantidade": 8.0}],
            itens_avulsos=[],
            observacoes="Rascunho Bar atualizado"
        )
        self.assertEqual(draft_id1, draft_id2, "Deve atualizar o mesmo ID de rascunho no mesmo dia")

        draft_updated = database.get_draft_by_sector(user_bar["id"])
        self.assertEqual(draft_updated["itens_catalogo"][0]["quantidade_pedida"], 8.0)
        self.assertEqual(len(draft_updated["itens_avulsos"]), 0)
        self.assertEqual(draft_updated["observacoes"], "Rascunho Bar atualizado")

        # 6. Finalizar e enviar o pedido
        final_id = database.finalize_draft_or_create_order(
            usuario_id=user_bar["id"],
            itens_catalogo=[{"produto_id": p1["id"], "quantidade": 8.0}],
            itens_avulsos=[],
            observacoes="Pedido final Bar"
        )
        self.assertEqual(final_id, draft_id1)

        # 7. Rascunho não deve mais existir como aberto
        draft_after_final = database.get_draft_by_sector(user_bar["id"])
        self.assertIsNone(draft_after_final)

        # 8. Agora DEVE aparecer na administração com status Pendente
        admin_orders_after = database.get_orders_by_date(today)
        final_order = next((o for o in admin_orders_after if o["id"] == final_id), None)
        self.assertIsNotNone(final_order)
        self.assertEqual(final_order["status"], "Pendente")

    def test_15_whatsapp_formatting_and_copy_assets(self):
        """Verifica a presença das rotinas e formatação do botão WhatsApp em admin.html e app.js."""
        # 1. Verifica admin.html
        admin_html_path = os.path.join(os.path.dirname(__file__), "templates", "admin.html")
        with open(admin_html_path, "r", encoding="utf-8") as f:
            admin_content = f.read()

        self.assertIn("copyWhatsAppList()", admin_content)
        self.assertIn("copiedWhatsApp", admin_content)
        self.assertIn("buildWhatsAppConsolidatedText", admin_content)
        self.assertIn("copyTextToClipboard", admin_content)

        # 2. Verifica static/js/app.js
        app_js_path = os.path.join(os.path.dirname(__file__), "static", "js", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            js_content = f.read()

        self.assertIn("function buildWhatsAppConsolidatedText", js_content)
        self.assertIn("📋 *ORDEM CONSOLIDADA DE COMPRAS - GRANODOC*", js_content)
        self.assertIn("📦 *INSUMOS OFICIAIS:*", js_content)
        self.assertIn("🛒 *ITENS AVULSOS / EXTRAS:*", js_content)
        self.assertIn("Total de itens:", js_content)
        self.assertIn("function copyTextToClipboard", js_content)
        self.assertIn("execCommand('copy')", js_content)

    def test_16_daily_orders_pdf_generation(self):
        """Testa a geração de relatórios PDF individuais e consolidados por praça da Aba 1."""
        today = datetime.now().strftime("%Y-%m-%d")
        orders = database.get_orders_by_date(today)

        # 1. Teste de PDF Individual da Praça (ex: Pizza)
        pdf_pizza_buffer = pdf_generator.generate_daily_orders_pdf(orders=orders, date_str=today, sector="Pizza")
        self.assertIsNotNone(pdf_pizza_buffer)
        pdf_pizza_bytes = pdf_pizza_buffer.getvalue()
        self.assertTrue(pdf_pizza_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_pizza_bytes), 1500)

        # 2. Teste de PDF Geral Diário com quebra por praça
        pdf_general_buffer = pdf_generator.generate_daily_orders_pdf(orders=orders, date_str=today, sector=None)
        self.assertIsNotNone(pdf_general_buffer)
        pdf_general_bytes = pdf_general_buffer.getvalue()
        self.assertTrue(pdf_general_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_general_bytes), 1500)

        # 3. Teste de PDF vazio (sem pedidos na data)
        pdf_empty_buffer = pdf_generator.generate_daily_orders_pdf(orders=[], date_str="2020-01-01", sector="Bar")
        self.assertIsNotNone(pdf_empty_buffer)
        pdf_empty_bytes = pdf_empty_buffer.getvalue()
        self.assertTrue(pdf_empty_bytes.startswith(b"%PDF"))

        # 4. Verifica templates e rotas
        app_path = os.path.join(os.path.dirname(__file__), "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            app_content = f.read()
        self.assertIn('@app.get("/api/admin/orders/pdf")', app_content)

        admin_html_path = os.path.join(os.path.dirname(__file__), "templates", "admin.html")
        with open(admin_html_path, "r", encoding="utf-8") as f:
            admin_content = f.read()
        self.assertIn("Exportar Todos em PDF (Por Praça)", admin_content)
        self.assertIn("/api/admin/orders/pdf?date=", admin_content)

    def test_17_order_status_transitions_and_batch_date(self):
        """Testa a transição de status individual e em lote por data (Aba 1 e Aba 2)."""
        today = datetime.now().strftime("%Y-%m-%d")
        user_pizza = database.authenticate_user("Pizza", "1001")
        user_cozinha = database.authenticate_user("Cozinha", "1002")

        prods_pizza = database.get_products(setor="Pizza")
        prods_cozinha = database.get_products(setor="Cozinha")

        # Cria pedidos para teste de status
        p1 = database.create_order(
            usuario_id=user_pizza["id"],
            itens_catalogo=[{"produto_id": prods_pizza[0]["id"], "quantidade": 2.0}],
            itens_avulsos=[]
        )
        p2 = database.create_order(
            usuario_id=user_cozinha["id"],
            itens_catalogo=[{"produto_id": prods_cozinha[0]["id"], "quantidade": 4.0}],
            itens_avulsos=[]
        )

        # 1. Teste individual: Transição Pendente -> Aprovado
        self.assertTrue(database.update_order_status(p1, "Aprovado"))
        det1 = database.get_order_details(p1)
        self.assertEqual(det1["status"], "Aprovado")

        # 2. Teste individual: Transição Aprovado -> Comprado
        self.assertTrue(database.update_order_status(p1, "Comprado"))
        det1_comprado = database.get_order_details(p1)
        self.assertEqual(det1_comprado["status"], "Comprado")

        # 3. Teste em lote (Aba 2): Marcar todos do dia como Aprovados
        count_aprovados = database.update_orders_status_by_date(today, "Aprovado")
        self.assertGreaterEqual(count_aprovados, 2)
        orders_today = database.get_orders_by_date(today)
        self.assertTrue(all(o["status"] == "Aprovado" for o in orders_today if o["id"] in (p1, p2)))

        # 4. Teste em lote (Aba 2): Marcar todos do dia como Comprados
        count_comprados = database.update_orders_status_by_date(today, "Comprado")
        self.assertGreaterEqual(count_comprados, 2)
        # Aba 1 e Aba 2 filtram apenas pedidos ativos ('Pendente', 'Aprovado').
        # Portanto, pedidos marcados como Comprados são excluídos da listagem diária padrão
        orders_today_active = database.get_orders_by_date(today)
        self.assertFalse(any(o["id"] in (p1, p2) for o in orders_today_active))

        # E aparecem exclusivamente nos pedidos concluídos (Aba 5)
        completed_orders = database.get_completed_orders(date_str=today)
        completed_ids = [o["id"] for o in completed_orders]
        self.assertIn(p1, completed_ids)
        self.assertIn(p2, completed_ids)
        self.assertTrue(all(o["status"] == "Comprado" for o in completed_orders if o["id"] in (p1, p2)))

        # 5. Verifica endpoints e frontend
        app_path = os.path.join(os.path.dirname(__file__), "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            app_code = f.read()
        self.assertIn("/api/admin/orders/{pedido_id}/status", app_code)
        self.assertIn("/api/pedidos/{pedido_id}/status", app_code)
        self.assertIn("/api/admin/orders/batch-status-by-date", app_code)
        self.assertIn("/api/admin/orders/completed", app_code)
        self.assertIn("/api/admin/orders/completed/pdf", app_code)
        self.assertIn("/api/admin/orders/{pedido_id}/reopen", app_code)

        admin_path = os.path.join(os.path.dirname(__file__), "templates", "admin.html")
        with open(admin_path, "r", encoding="utf-8") as f:
            admin_code = f.read()
        self.assertIn("changeStatus(order.id", admin_code)
        self.assertIn("changeAllStatusForDate('Aprovado')", admin_code)
        self.assertIn("changeAllStatusForDate('Comprado')", admin_code)
        self.assertIn("changeStatus(orderId, newStatus)", admin_code)
        self.assertIn("changeAllStatusForDate(newStatus)", admin_code)
        self.assertIn("recalculateDailyStats()", admin_code)
        self.assertIn("Aba 5: Pedidos Concluídos", admin_code)
        self.assertIn("reopenOrder", admin_code)

    def test_18_completed_orders_tab_and_exclusion(self):
        """Valida a Aba 5 (Pedidos Concluídos), exclusão na Aba 1 e 2, reabertura e PDF."""
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. Cria pedido para Pizza
        user_pizza = database.get_user_by_sector("Pizza")
        prods = database.get_products(setor="Pizza", active_only=True)
        prod = prods[0] if prods else {"id": 1}
        p_id = database.finalize_draft_or_create_order(
            usuario_id=user_pizza["id"],
            itens_catalogo=[{"produto_id": prod["id"], "quantidade": 5.0}],
            itens_avulsos=[{"descricao": "Item Avulso Concluido Teste", "quantidade": 2.0, "unidade_medida": "un"}],
            observacoes="Teste de Conclusão e Arquivamento"
        )

        # Confirma que aparece na Aba 1 inicialmente (Pendente)
        orders_active = database.get_orders_by_date(today)
        self.assertTrue(any(o["id"] == p_id for o in orders_active))

        # 2. Marca como 'Comprado' via banco
        self.assertTrue(database.update_order_status(p_id, "Comprado"))

        # 3. Verifica que SUMIU da Aba 1 (Pedidos por Data) e da Aba 2 (Consolidação)
        orders_active_after = database.get_orders_by_date(today)
        self.assertFalse(any(o["id"] == p_id for o in orders_active_after))

        consolidado = database.get_consolidated_orders(today)
        self.assertFalse(any(a.get("descricao_item") == "Item Avulso Concluido Teste" for a in consolidado.get("avulsos", [])))

        # 4. Verifica que APARECE nos pedidos concluídos (Aba 5)
        comp_list = database.get_completed_orders(date_str=today, setor="Pizza")
        self.assertTrue(any(o["id"] == p_id for o in comp_list))
        order_comp = next(o for o in comp_list if o["id"] == p_id)
        self.assertEqual(order_comp["status"], "Comprado")
        self.assertEqual(len(order_comp["itens_catalogo"]), 1)
        self.assertEqual(len(order_comp["itens_avulsos"]), 1)

        # 5. Testa geração do PDF da Aba 5
        pdf_buf = pdf_generator.generate_completed_orders_pdf(
            orders=comp_list,
            date_str=today,
            sector="Pizza"
        )
        self.assertIsNotNone(pdf_buf)
        pdf_bytes = pdf_buf.getvalue()
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

        # 6. Testa Reabrir Pedido (reverte para Aprovado)
        self.assertTrue(database.update_order_status(p_id, "Aprovado"))

        # Verifica que retornou para a Aba 1 e Aba 2
        orders_reopened = database.get_orders_by_date(today)
        self.assertTrue(any(o["id"] == p_id and o["status"] == "Aprovado" for o in orders_reopened))

        # E sumiu da Aba 5
        comp_after = database.get_completed_orders(date_str=today, setor="Pizza")
        self.assertFalse(any(o["id"] == p_id for o in comp_after))

if __name__ == "__main__":
    unittest.main()



