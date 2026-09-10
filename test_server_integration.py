import os
import sys
import time
import urllib.request
import urllib.parse
import json
import http.cookiejar
from datetime import datetime

BASE_URL = "http://127.0.0.1:8001"

def run_integration_tests():
    # Prepara cookie jar para manter sessão entre requisições
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    print("\n--- INICIANDO TESTES DE INTEGRAÇÃO HTTP ---")

    # 1. Teste GET /login
    req = urllib.request.Request(f"{BASE_URL}/login")
    with opener.open(req) as resp:
        html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "Pedidos Granodoc" in html
        assert "Identificação de Acesso" in html
        print("[OK] 1. GET /login respondeu 200 OK com HTML valido.")

    # 2. Teste POST /api/login (Pizzaiolo - PIN 1001)
    login_data = json.dumps({"setor": "Pizza", "pin": "1001"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as resp:
        res_json = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert res_json["success"] is True
        assert res_json["user"]["nome_setor"] == "Pizza"
        print("[OK] 2. POST /api/login (Pizza, PIN 1001) autenticou com sucesso.")

    # 3. Teste GET /api/products/sector (deve trazer catálogo de Pizza)
    req = urllib.request.Request(f"{BASE_URL}/api/products/sector")
    with opener.open(req) as resp:
        prods = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert len(prods) >= 8
        for p in prods:
            assert p["setor_responsavel"] == "Pizza"
        print(f"[OK] 3. GET /api/products/sector retornou {len(prods)} produtos da Praca Pizza.")

    # 4. Teste POST /api/orders (Enviar pedido de Pizza)
    order_data = json.dumps({
        "itens_catalogo": [
            {"produto_id": prods[0]["id"], "quantidade": 5.0},
            {"produto_id": prods[1]["id"], "quantidade": 3.0}
        ],
        "itens_avulsos": [
            {"descricao": "Oregano Peruano Desidratado", "quantidade": 2.0, "unidade_medida": "pct"}
        ],
        "observacoes": "Massa do turno da noite, entregar no almoxarifado."
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/orders",
        data=order_data,
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as resp:
        order_res = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert order_res["success"] is True
        order_id = order_res["pedido_id"]
        print(f"[OK] 4. POST /api/orders criou o Pedido #{order_id} com sucesso.")

    # 5. Teste GET /api/orders/recent (Histórico 7 dias da praça)
    req = urllib.request.Request(f"{BASE_URL}/api/orders/recent?days=7")
    with opener.open(req) as resp:
        recents = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert any(o["id"] == order_id for o in recents)
        print(f"[OK] 5. GET /api/orders/recent retornou {len(recents)} pedidos no historico da praca.")

    # 6. Teste POST /api/login com Barman (PIN 1003) para criar outro pedido
    bar_cookie_jar = http.cookiejar.CookieJar()
    bar_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(bar_cookie_jar))
    login_bar = json.dumps({"setor": "Bar", "pin": "1003"}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/login", data=login_bar, headers={"Content-Type": "application/json"})
    with bar_opener.open(req) as resp:
        assert resp.status == 200

    req = urllib.request.Request(f"{BASE_URL}/api/products/sector")
    with bar_opener.open(req) as resp:
        bar_prods = json.loads(resp.read().decode("utf-8"))

    order_bar_data = json.dumps({
        "itens_catalogo": [
            {"produto_id": bar_prods[0]["id"], "quantidade": 4.0}
        ],
        "itens_avulsos": [],
        "observacoes": "Reposicao para drinks autorais"
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/orders", data=order_bar_data, headers={"Content-Type": "application/json"})
    with bar_opener.open(req) as resp:
        assert resp.status == 200
        print("[OK] 6. Pedido do Bar registrado para testar consolidacao multi-pracas.")

    # 7. Teste Login Administração (PIN 9999)
    admin_cookie_jar = http.cookiejar.CookieJar()
    admin_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(admin_cookie_jar))
    login_admin = json.dumps({"setor": "Administracao", "pin": "9999"}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/login", data=login_admin, headers={"Content-Type": "application/json"})
    with admin_opener.open(req) as resp:
        admin_res = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert admin_res["user"]["nivel_acesso"] == "admin"
        print("[OK] 7. POST /api/login (Administracao, PIN 9999) autenticou com sucesso.")

    # 8. Teste GET /api/admin/consolidated (Consolidação Unificada de Compras)
    hoje = datetime.now().strftime("%Y-%m-%d")
    req = urllib.request.Request(f"{BASE_URL}/api/admin/consolidated?date={hoje}")
    with admin_opener.open(req) as resp:
        consolidado = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert len(consolidado["catalogo"]) >= 2
        assert len(consolidado["avulsos"]) >= 1
        assert consolidado["resumo"]["total_pedidos"] >= 2
        print("[OK] 8. GET /api/admin/consolidated agrupou itens de Pizza e Bar unificados!")

    # 9. Teste PATCH /api/admin/orders/{id}/status (Alterar para Aprovado)
    status_data = json.dumps({"status": "Aprovado"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/admin/orders/{order_id}/status",
        data=status_data,
        headers={"Content-Type": "application/json"},
        method="PATCH"
    )
    with admin_opener.open(req) as resp:
        status_res = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert status_res["new_status"] == "Aprovado"
        print(f"[OK] 9. PATCH /api/admin/orders/{order_id}/status atualizou para 'Aprovado'.")

    # 10. Teste GET /api/admin/consolidated/pdf (Geração de PDF ReportLab)
    req = urllib.request.Request(f"{BASE_URL}/api/admin/consolidated/pdf?date={hoje}")
    with admin_opener.open(req) as resp:
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "application/pdf" in content_type
        pdf_bytes = resp.read()
        assert pdf_bytes.startswith(b"%PDF")
        print(f"[OK] 10. GET /api/admin/consolidated/pdf gerou {len(pdf_bytes)} bytes de PDF valido.")

    print("\nTODOS OS 10 TESTES DE INTEGRACAO PASSARAM COM SUCESSO!\n")

if __name__ == "__main__":
    run_integration_tests()
