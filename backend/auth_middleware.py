# ============================================================
# auth_middleware.py — Verificación de tokens JWT de Supabase
# El backend valida que el request viene de un usuario logueado
# ============================================================

import os
import jwt
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

security = HTTPBearer(auto_error=False)


def verify_token(credentials: HTTPAuthorizationCredentials) -> dict:
    """
    Verifica el JWT emitido por Supabase Auth.
    Retorna el payload del token si es válido.
    Lanza HTTPException 401 si no lo es.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="No autenticado — inicia sesión")

    if not SUPABASE_JWT_SECRET:
        # En desarrollo local sin JWT secret configurado,
        # solo verificamos que el token existe (no su firma).
        # EN PRODUCCIÓN esto nunca debería ocurrir.
        import os
        if os.getenv("RENDER"):
            raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET no configurado")
        # Modo desarrollo: decodificar sin verificar firma
        try:
            payload = jwt.decode(
                credentials.credentials,
                options={"verify_signature": False}
            )
            return payload
        except Exception:
            raise HTTPException(status_code=401, detail="Token inválido")

    try:
        payload = jwt.decode(
            credentials.credentials,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada — vuelve a iniciar sesión")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = None
) -> dict:
    """
    Dependencia de FastAPI para proteger endpoints.
    Uso: user = Depends(get_current_user)
    """
    return verify_token(credentials)
