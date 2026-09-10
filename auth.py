import secrets
import hmac
import hashlib
import json
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
import database

SECRET_KEY = "granodoc_super_secret_session_key_2026"
SESSION_COOKIE_NAME = "granodoc_session"
AUDIT_COOKIE_NAME = "granodoc_audit_sector"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 dias

# Cache de sessões em memória com timestamp de expiração
_ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

def create_session(user: Dict[str, Any]) -> str:
    """Cria um token de sessão e armazena os dados do usuário autenticado."""
    token = secrets.token_urlsafe(32)
    _ACTIVE_SESSIONS[token] = {
        "user_id": user["id"],
        "nome_setor": user["nome_setor"],
        "nivel_acesso": user["nivel_acesso"],
        "icone": user.get("icone", "utensils"),
        "descricao": user.get("descricao", ""),
        "created_at": time.time(),
        "expires_at": time.time() + SESSION_MAX_AGE_SECONDS,
    }
    return token

def get_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Recupera e valida a sessão pelo token."""
    if not token or token not in _ACTIVE_SESSIONS:
        return None
    session_data = _ACTIVE_SESSIONS[token]
    if time.time() > session_data.get("expires_at", 0):
        # Expirada
        del _ACTIVE_SESSIONS[token]
        return None
    return session_data

def destroy_session(token: Optional[str]) -> None:
    if token and token in _ACTIVE_SESSIONS:
        del _ACTIVE_SESSIONS[token]

def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """Extrai o usuário atual a partir do cookie ou do header Authorization."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()

    session_data = get_session(token)
    if not session_data:
        return None

    user = database.get_user_by_id(session_data["user_id"])
    if not user:
        return None

    # Verifica se há modo de auditoria ativo para administrador
    audit_sector = request.cookies.get(AUDIT_COOKIE_NAME)
    if user["nivel_acesso"] == "admin" and audit_sector:
        user["audit_mode_active"] = True
        user["audit_sector"] = audit_sector
    else:
        user["audit_mode_active"] = False
        user["audit_sector"] = None

    return user

async def require_authenticated_user(request: Request) -> Dict[str, Any]:
    """Dependency para rotas de API que exigem qualquer usuário logado."""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado. Por favor insira seu PIN de acesso."
        )
    return user

async def require_admin_user(request: Request) -> Dict[str, Any]:
    """Dependency para rotas que exigem perfil Administrador."""
    user = await require_authenticated_user(request)
    if user.get("nivel_acesso") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à Administração."
        )
    return user

def check_sector_permission(user: Dict[str, Any], target_sector: str) -> bool:
    """Regra RBAC: Operadores só acessam seu próprio setor. Admin acessa tudo."""
    if user.get("nivel_acesso") == "admin":
        return True
    return user.get("nome_setor", "").lower() == target_sector.lower()
