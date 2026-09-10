import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends, status, Query, Response, File, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import database
import auth
import pdf_generator
import template_generator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa banco de dados com schema e seeds ao iniciar
    database.init_db()
    yield

app = FastAPI(
    title="Pedidos Granodoc - Suprimentos",
    description="Sistema de Gestão de Compras Internas e Requisições de Insumos",
    version="1.0.0",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- PYDANTIC SCHEMAS ---

class LoginRequest(BaseModel):
    setor: Optional[str] = None
    pin: str = Field(..., min_length=4, max_length=4)

class ItemCatalogoInput(BaseModel):
    produto_id: int
    quantidade: float = Field(..., gt=0)

class ItemAvulsoInput(BaseModel):
    descricao: str
    quantidade: float = Field(..., gt=0)
    unidade_medida: str = "un"

class OrderCreateRequest(BaseModel):
    itens_catalogo: List[ItemCatalogoInput] = []
    itens_avulsos: List[ItemAvulsoInput] = []
    observacoes: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: str

class BatchStatusByDateRequest(BaseModel):
    date: str
    status: str

class CategoryCreateRequest(BaseModel):
    nome: str = Field(..., min_length=1)
    setor: str = Field(..., min_length=1)

class ProductCreateRequest(BaseModel):
    nome: str
    setor: Optional[str] = None
    setores: Optional[List[str]] = None
    unidade: str
    categoria: Optional[str] = "Geral"

class ProductUpdateRequest(BaseModel):
    nome: str
    setor: Optional[str] = None
    setores: Optional[List[str]] = None
    unidade: str
    categoria: Optional[str] = "Geral"

class ProductToggleRequest(BaseModel):
    ativo: bool

class BatchProductItem(BaseModel):
    nome: str
    setor: Optional[str] = None
    unidade: Optional[str] = "un"
    categoria: Optional[str] = "Geral"

class BatchProductsRequest(BaseModel):
    setor: str
    raw_text: Optional[str] = None
    produtos: Optional[List[BatchProductItem]] = None
    default_categoria: Optional[str] = "Geral"
    default_unidade: Optional[str] = "un"

class BatchDeleteProductsRequest(BaseModel):
    product_ids: List[int] = Field(..., min_length=1)


# --- ROTAS DE PÁGINAS (HTML) ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Roteamento inteligente inicial baseado na sessão e perfil do usuário."""
    user = auth.get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if user["nivel_acesso"] == "admin" and not user.get("audit_mode_active"):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    return RedirectResponse(url="/operator", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Tela de login com teclado numérico de PIN."""
    user = auth.get_current_user_from_request(request)
    if user:
        if user["nivel_acesso"] == "admin" and not user.get("audit_mode_active"):
            return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/operator", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"current_user": None}
    )

@app.get("/logout")
async def logout():
    """Encerra a sessão e remove os cookies de autenticação e auditoria."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(auth.SESSION_COOKIE_NAME)
    response.delete_cookie(auth.AUDIT_COOKIE_NAME)
    return response

@app.get("/operator", response_class=HTMLResponse)
async def operator_page(request: Request):
    """Interface operacional da praça (Pizzaiolo, Cozinha, Bar, Salão)."""
    user = auth.get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Se for admin sem modo auditoria, redireciona para o painel Master
    if user["nivel_acesso"] == "admin" and not user.get("audit_mode_active"):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    # Se for admin em modo auditoria, personaliza a visão para o setor auditado
    if user.get("audit_mode_active"):
        target_sector = user.get("audit_sector", "Pizza")
        audit_user = database.get_user_by_sector(target_sector)
        display_user = {
            "id": audit_user["id"] if audit_user else user["id"],
            "nome_setor": target_sector,
            "nivel_acesso": "operador",
            "icone": audit_user["icone"] if audit_user else "utensils",
            "descricao": audit_user["descricao"] if audit_user else "",
            "audit_mode_active": True,
            "audit_sector": target_sector
        }
    else:
        display_user = user

    return templates.TemplateResponse(
        request=request,
        name="operator.html",
        context={"current_user": display_user}
    )

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Painel Master da Administração."""
    user = auth.get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if user.get("nivel_acesso") != "admin":
        # Bloqueia operadores de acessarem a administração (RBAC)
        return RedirectResponse(url="/operator", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"current_user": user}
    )

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Página separada de Indicadores & Estatísticas da Administração."""
    user = auth.get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if user.get("nivel_acesso") != "admin":
        return RedirectResponse(url="/operator", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={"current_user": user}
    )



# --- ROTAS DE API: AUTENTICAÇÃO ---

@app.post("/api/login")
async def api_login(req: LoginRequest, response: Response):
    """Validação de PIN com retorno de token de sessão em cookie seguro."""
    user = None
    if req.setor:
        user = database.authenticate_user(req.setor, req.pin)
    else:
        user = database.authenticate_by_pin_only(req.pin)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN incorreto para a praça selecionada."
        )

    token = auth.create_session(user)
    response.set_cookie(
        key=auth.SESSION_COOKIE_NAME,
        value=token,
        max_age=auth.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )

    # Limpa cookie de auditoria anterior
    response.delete_cookie(auth.AUDIT_COOKIE_NAME)

    redirect_url = "/admin" if user["nivel_acesso"] == "admin" else "/operator"
    return {
        "success": True,
        "user": user,
        "redirect_url": redirect_url
    }


# --- ROTAS DE API: OPERACIONAL (PRAÇAS) ---

@app.get("/api/products/sector")
async def api_products_sector(request: Request, current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)):
    """Retorna os produtos do catálogo correspondentes ao setor do usuário logado."""
    target_sector = current_user["nome_setor"]
    if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
        target_sector = current_user["audit_sector"]

    products = database.get_products(setor=target_sector, active_only=True)
    return products

@app.get("/api/orders/draft")
async def api_get_order_draft(
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Retorna o rascunho de pedido ativo da praça para hoje, se houver."""
    user_id = current_user["id"]
    if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
        sector_user = database.get_user_by_sector(current_user["audit_sector"])
        if sector_user:
            user_id = sector_user["id"]

    draft = database.get_draft_by_sector(usuario_id=user_id)
    return {
        "has_draft": draft is not None,
        "draft": draft
    }

@app.post("/api/orders/draft")
async def api_save_order_draft(
    order_data: OrderCreateRequest,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Salva ou atualiza um rascunho de pedido da praça (máximo 1 rascunho por data)."""
    if not order_data.itens_catalogo and not order_data.itens_avulsos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O rascunho deve conter pelo menos um item de catálogo ou avulso."
        )

    user_id = current_user["id"]
    if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
        sector_user = database.get_user_by_sector(current_user["audit_sector"])
        if sector_user:
            user_id = sector_user["id"]

    try:
        pedido_id = database.save_order_draft(
            usuario_id=user_id,
            itens_catalogo=[item.model_dump() for item in order_data.itens_catalogo],
            itens_avulsos=[avulso.model_dump() for avulso in order_data.itens_avulsos],
            observacoes=order_data.observacoes
        )
        return {
            "success": True,
            "pedido_id": pedido_id,
            "message": "Rascunho salvo com sucesso! Você pode continuar editando mais tarde."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar rascunho: {str(e)}"
        )

@app.post("/api/orders")
async def api_create_order(
    order_data: OrderCreateRequest,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Finaliza e envia um pedido da praça com status Pendente (convertendo rascunho se existir)."""
    if not order_data.itens_catalogo and not order_data.itens_avulsos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O pedido deve conter pelo menos um item de catálogo ou avulso."
        )

    # Define o id do usuário (se for auditoria, vincula ao usuário daquela praça)
    user_id = current_user["id"]
    if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
        sector_user = database.get_user_by_sector(current_user["audit_sector"])
        if sector_user:
            user_id = sector_user["id"]

    try:
        pedido_id = database.finalize_draft_or_create_order(
            usuario_id=user_id,
            itens_catalogo=[item.model_dump() for item in order_data.itens_catalogo],
            itens_avulsos=[avulso.model_dump() for avulso in order_data.itens_avulsos],
            observacoes=order_data.observacoes
        )
        return {
            "success": True,
            "pedido_id": pedido_id,
            "message": "Pedido enviado com sucesso para a administração!"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar pedido: {str(e)}"
        )

@app.get("/api/orders/recent")
async def api_recent_orders(
    days: int = Query(7, ge=1, le=30),
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Retorna os pedidos recentes da praça nos últimos X dias."""
    user_id = current_user["id"]
    if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
        sector_user = database.get_user_by_sector(current_user["audit_sector"])
        if sector_user:
            user_id = sector_user["id"]

    orders = database.get_recent_orders_by_user(user_id=user_id, days=days)
    return orders


# --- ROTAS DE API: ADMINISTRAÇÃO (MASTER) ---

@app.get("/api/admin/orders/by-date")
async def api_admin_orders_by_date(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    setor: Optional[str] = Query("todos"),
    status_filter: Optional[str] = Query("todos", alias="status"),
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """Retorna todos os pedidos da data selecionada com opções de filtro."""
    orders = database.get_orders_by_date(date_str=date, setor=setor, status=status_filter)
    return orders

@app.patch("/api/admin/orders/{pedido_id}/status")
@app.patch("/api/pedidos/{pedido_id}/status")
async def api_admin_update_status(
    pedido_id: int,
    req: StatusUpdateRequest,
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """Altera o status do pedido individual (Pendente -> Aprovado -> Comprado)."""
    if req.status not in ("Pendente", "Aprovado", "Comprado"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status inválido. Escolha entre: Pendente, Aprovado, Comprado."
        )

    success = database.update_order_status(pedido_id, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    return {"success": True, "pedido_id": pedido_id, "new_status": req.status}

@app.patch("/api/admin/orders/batch-status-by-date")
@app.post("/api/admin/orders/batch-status-by-date")
@app.patch("/api/pedidos/batch-status-by-date")
@app.post("/api/pedidos/batch-status-by-date")
async def api_admin_batch_status_by_date(
    req: BatchStatusByDateRequest,
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """Altera o status de todos os pedidos ativos de uma data especificada (Aba 2)."""
    if req.status not in ("Pendente", "Aprovado", "Comprado"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status inválido. Escolha entre: Pendente, Aprovado, Comprado."
        )

    count = database.update_orders_status_by_date(req.date, req.status)
    return {
        "success": True,
        "date": req.date,
        "new_status": req.status,
        "updated_orders_count": count
    }

@app.get("/api/admin/consolidated")
async def api_admin_consolidated(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    status_filter: Optional[str] = Query("todos", alias="status"),
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """Gera a consolidação SQL unificada de todos os setores para a data especificada."""
    data = database.get_consolidated_orders(date_str=date, status_filter=status_filter)
    return data

@app.get("/api/admin/consolidated/pdf")
async def api_admin_consolidated_pdf(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """Gera e faz download da ordem de compra consolidada em PDF com ReportLab."""
    consolidated_data = database.get_consolidated_orders(date_str=date)
    pdf_buffer = pdf_generator.generate_consolidated_pdf(consolidated_data)

    filename = f"pedidos_granodoc_consolidado_{date}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )

@app.get("/api/admin/orders/pdf")
async def api_admin_orders_pdf(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sector: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """
    Gera e faz download do relatório PDF dos pedidos diários (Aba 1).
    Suporta exportação individual por praça ou relatório geral diário consolidado por página.
    """
    orders = database.get_orders_by_date(date_str=date, setor=sector)
    pdf_buffer = pdf_generator.generate_daily_orders_pdf(orders=orders, date_str=date, sector=sector)

    parts = date.split("-")
    date_formatted = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else date

    if sector and sector.lower() != "todos":
        clean_sector = sector.strip().replace(" ", "_")
        filename = f"Pedido_{clean_sector}_{date_formatted}.pdf"
    else:
        filename = f"Pedidos_Diarios_Granodoc_{date_formatted}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )

@app.get("/api/admin/orders/completed")
async def api_admin_orders_completed(
    date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    setor: Optional[str] = Query("todos"),
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """
    Retorna os pedidos concluídos (status = 'Comprado') para a Aba 5.
    Permite filtrar por data específica ou intervalo (start_date/end_date) e praça.
    """
    orders = database.get_completed_orders(
        date_str=date,
        start_date=start_date,
        end_date=end_date,
        setor=setor
    )
    return orders

@app.get("/api/admin/orders/completed/pdf")
async def api_admin_orders_completed_pdf(
    date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    setor: Optional[str] = Query("todos"),
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """
    Gera e faz download do relatório PDF dos pedidos concluídos / histórico de compras (Aba 5).
    """
    orders = database.get_completed_orders(
        date_str=date,
        start_date=start_date,
        end_date=end_date,
        setor=setor
    )
    pdf_buffer = pdf_generator.generate_completed_orders_pdf(
        orders=orders,
        date_str=date,
        start_date=start_date,
        end_date=end_date,
        sector=setor
    )

    filename_parts = ["Pedidos_Concluidos"]
    if setor and setor.lower() != "todos":
        filename_parts.append(setor.strip().replace(" ", "_"))
    if date:
        filename_parts.append(date)
    elif start_date and end_date:
        filename_parts.append(f"{start_date}_a_{end_date}")
    else:
        filename_parts.append(datetime.now().strftime("%Y%m%d"))

    filename = f"{'_'.join(filename_parts)}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )

@app.post("/api/admin/orders/{pedido_id}/reopen")
async def api_admin_reopen_order(
    pedido_id: int,
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """
    Reabre um pedido concluído, revertendo seu status para 'Aprovado'.
    Retorna o pedido para a Aba 1 e Aba 2.
    """
    success = database.update_order_status(pedido_id, "Aprovado")
    if not success:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return {"success": True, "pedido_id": pedido_id, "new_status": "Aprovado"}

@app.get("/api/admin/analytics")
async def api_admin_analytics(
    period_type: str = Query("month", pattern="^(month|semester_1|semester_2|year)$"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    sector: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """Retorna indicadores agregados (quantidade, soma, médias) e ranking Top 10."""
    return database.get_analytics_data(
        period_type=period_type,
        year=year,
        month=month,
        sector=sector
    )

# --- ROTAS DE CATEGORIAS ---

@app.get("/api/categories")
async def api_get_categories(
    setor: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Retorna as categorias de produtos de um setor específico ou de todos."""
    target_setor = setor
    if current_user["nivel_acesso"] != "admin" and not target_setor:
        target_setor = current_user["nome_setor"]
    if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
        target_setor = current_user["audit_sector"]
    return database.get_categories_by_sector(target_setor)

@app.post("/api/categories")
async def api_create_category(
    req: CategoryCreateRequest,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Cria uma nova categoria para o setor."""
    if current_user["nivel_acesso"] != "admin":
        active_sector = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            active_sector = current_user["audit_sector"]
        if req.setor.lower() != active_sector.lower():
            raise HTTPException(status_code=403, detail="Você só pode criar categorias para sua própria praça.")

    cat_id = database.create_category(nome=req.nome, setor=req.setor)
    return {"success": True, "categoria_id": cat_id, "nome": req.nome, "setor": req.setor}

@app.delete("/api/categories/{cat_id}")
async def api_delete_category(
    cat_id: int,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Exclui uma categoria, reassociando seus produtos para 'Geral'."""
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT setor FROM categorias WHERE id = ?", (cat_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    if current_user["nivel_acesso"] != "admin":
        active_sector = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            active_sector = current_user["audit_sector"]
        if row["setor"].lower() != active_sector.lower():
            raise HTTPException(status_code=403, detail="Você só pode excluir categorias da sua própria praça.")

    success = database.delete_category(cat_id)
    return {"success": success}

# --- ROTAS DE GESTÃO DE PRODUTOS ---

@app.get("/api/admin/products/all")
async def api_admin_all_products(
    setor: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Retorna produtos do catálogo (ativos e inativos) para gestão."""
    target_setor = setor
    if current_user["nivel_acesso"] != "admin":
        target_setor = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            target_setor = current_user["audit_sector"]
    return database.get_products(setor=target_setor, active_only=False)

@app.post("/api/products")
@app.post("/api/admin/products")
async def api_create_product(
    req: ProductCreateRequest,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Cadastra um novo produto no catálogo oficial."""
    target_setores = req.setores if req.setores else ([req.setor] if req.setor else [])
    if not target_setores:
        raise HTTPException(status_code=400, detail="Pelo menos uma praça deve ser selecionada.")

    if current_user["nivel_acesso"] != "admin":
        active_sector = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            active_sector = current_user["audit_sector"]
        if any(s.lower() != active_sector.lower() for s in target_setores):
            raise HTTPException(status_code=403, detail="Você só pode cadastrar insumos para sua própria praça.")

    new_id = database.create_product(
        nome=req.nome,
        setor=target_setores,
        unidade=req.unidade,
        categoria=req.categoria or "Geral"
    )
    return {"success": True, "produto_id": new_id, "setores": target_setores}

@app.put("/api/products/{prod_id}")
async def api_update_product(
    prod_id: int,
    req: ProductUpdateRequest,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Atualiza dados de um produto existente, incluindo nome, unidade, categoria e praças permitidas."""
    prod = database.get_product_by_id(prod_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    target_setores = req.setores if req.setores else ([req.setor] if req.setor else [])
    if not target_setores:
        raise HTTPException(status_code=400, detail="Pelo menos uma praça deve ser selecionada.")

    if current_user["nivel_acesso"] != "admin":
        active_sector = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            active_sector = current_user["audit_sector"]
        prod_sectors = [s.lower() for s in prod.get("setores", [prod["setor_responsavel"]])]
        if active_sector.lower() not in prod_sectors:
            raise HTTPException(status_code=403, detail="Você só pode editar insumos da sua própria praça.")

    success = database.update_product(
        prod_id=prod_id,
        nome=req.nome,
        setor=target_setores,
        unidade=req.unidade,
        categoria=req.categoria or "Geral"
    )
    return {"success": success, "setores": target_setores}

@app.delete("/api/products/{prod_id}")
async def api_delete_product(
    prod_id: int,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Exclui ou desativa com segurança um insumo do catálogo."""
    prod = database.get_product_by_id(prod_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    if current_user["nivel_acesso"] != "admin":
        active_sector = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            active_sector = current_user["audit_sector"]
        prod_sectors = [s.lower() for s in prod.get("setores", [prod["setor_responsavel"]])]
        if active_sector.lower() not in prod_sectors:
            raise HTTPException(status_code=403, detail="Você só pode excluir insumos da sua própria praça.")

    result = database.delete_product(prod_id)
    return result

@app.post("/api/admin/products/batch-delete")
async def api_admin_batch_delete_products(
    req: BatchDeleteProductsRequest,
    current_user: Dict[str, Any] = Depends(auth.require_admin_user)
):
    """Exclusão ou desativação em lote de produtos do catálogo (apenas administradores)."""
    result = database.delete_products_batch(req.product_ids)
    return result

@app.post("/api/products/batch")
async def api_create_products_batch(
    req: BatchProductsRequest,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Cadastro em lote de múltiplos insumos para carregar grandes catálogos rapidamente."""
    if current_user["nivel_acesso"] != "admin":
        active_sector = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            active_sector = current_user["audit_sector"]
        if req.setor.lower() != active_sector.lower():
            raise HTTPException(status_code=403, detail="Você só pode cadastrar insumos para sua própria praça.")

    items_to_insert = []

    # 1. Parse de texto colado (linha por linha)
    if req.raw_text:
        lines = req.raw_text.strip().splitlines()
        for idx_line, line in enumerate(lines):
            line_clean = line.strip()
            if not line_clean or line_clean.startswith("#"):
                continue

            # Ignora linha de cabeçalho da planilha se o usuário colar tudo
            if any(h in line_clean.lower() for h in ["nome do produto", "unidade de medida", "categoria", "praça (opcional)"]):
                continue

            # Delimitador: tab (\t), ponto-e-vírgula (;) ou vírgula (,)
            delimiter = "\t" if "\t" in line_clean else (";" if ";" in line_clean else ("," if "," in line_clean else None))
            if delimiter:
                parts = [p.strip() for p in line_clean.split(delimiter)]
                nome = parts[0]
                categoria = parts[1] if len(parts) > 1 and parts[1] else (req.default_categoria or "Geral")
                unidade = parts[2] if len(parts) > 2 and parts[2] else (req.default_unidade or "un")
                setor = parts[3] if len(parts) > 3 and parts[3] else req.setor
            else:
                nome = line_clean
                categoria = req.default_categoria or "Geral"
                unidade = req.default_unidade or "un"
                setor = req.setor

            if nome and nome.lower() not in ["nome do produto", "produto", "nome"]:
                items_to_insert.append({
                    "nome": nome,
                    "setor": setor or req.setor,
                    "unidade": unidade,
                    "categoria": categoria
                })

    # 2. Lista estruturada de produtos
    if req.produtos:
        for p in req.produtos:
            if p.nome and p.nome.strip():
                items_to_insert.append({
                    "nome": p.nome.strip(),
                    "setor": p.setor or req.setor,
                    "unidade": p.unidade or req.default_unidade or "un",
                    "categoria": p.categoria or req.default_categoria or "Geral"
                })

    if not items_to_insert:
        raise HTTPException(status_code=400, detail="Nenhum insumo válido identificado para cadastro.")

    result = database.create_products_batch(items_to_insert)
    return result


@app.get("/api/catalog/template/excel")
async def download_excel_template():
    """Download do modelo oficial de planilha Excel (.xlsx) para cadastro em lote."""
    excel_bytes = template_generator.generate_excel_bytes()
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="modelo_cadastro_insumos.xlsx"'}
    )


@app.get("/api/catalog/template/csv")
async def download_csv_template():
    """Download do modelo oficial de planilha CSV (.csv) com acentuação corrigida."""
    csv_bytes = template_generator.generate_csv_bytes()
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="modelo_cadastro_insumos.csv"'}
    )


@app.post("/api/products/upload-file")
async def api_upload_products_file(
    file: UploadFile = File(...),
    setor: Optional[str] = Form("Pizza"),
    default_categoria: Optional[str] = Form("Geral"),
    default_unidade: Optional[str] = Form("un"),
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Lê um arquivo .xlsx ou .csv enviado pelo usuário e cadastra todos os insumos de uma vez."""
    if current_user["nivel_acesso"] != "admin":
        active_sector = current_user["nome_setor"]
        if current_user.get("audit_mode_active") and current_user.get("audit_sector"):
            active_sector = current_user["audit_sector"]
        if setor.lower() != active_sector.lower():
            raise HTTPException(status_code=403, detail="Você só pode cadastrar insumos para sua própria praça.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio enviado.")

    items = template_generator.parse_uploaded_file(
        file_bytes=content,
        filename=file.filename,
        default_setor=setor,
        default_unidade=default_unidade or "un",
        default_categoria=default_categoria or "Geral"
    )

    if not items:
        raise HTTPException(status_code=400, detail="Nenhum insumo válido identificado na planilha enviada.")

    result = database.create_products_batch(items)
    return {
        "success": True,
        "count": result["count"],
        "filename": file.filename,
        "sample": [p["nome"] for p in items[:5]]
    }

@app.patch("/api/admin/products/{prod_id}/toggle")
async def api_admin_toggle_product(
    prod_id: int,
    req: ProductToggleRequest,
    current_user: Dict[str, Any] = Depends(auth.require_authenticated_user)
):
    """Ativa ou desativa um produto do catálogo."""
    success = database.toggle_product_status(prod_id, req.ativo)
    return {"success": success}

# --- ROTAS DE MODO AUDITORIA ---

@app.get("/api/audit/enter")
async def api_audit_enter(sector: str, response: Response, current_user: Dict[str, Any] = Depends(auth.require_admin_user)):
    """Permite ao administrador inspecionar o sistema exatamente como a praça indicada enxerga."""
    valid_sectors = ["Pizza", "Cozinha", "Bar", "Salão"]
    # Compatibilidade retroativa para 'Sommelier'
    if sector.lower() == "sommelier":
        sector = "Salão"
    target = next((s for s in valid_sectors if s.lower() == sector.lower()), None)
    if not target:
        raise HTTPException(status_code=400, detail="Setor de auditoria inválido.")

    response.set_cookie(key=auth.AUDIT_COOKIE_NAME, value=target, httponly=True, samesite="lax")
    return {"success": True, "sector": target}

@app.get("/api/audit/exit")
async def api_audit_exit(response: Response):
    """Sai do modo auditoria e retorna ao painel Master."""
    resp = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(auth.AUDIT_COOKIE_NAME)
    return resp


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
