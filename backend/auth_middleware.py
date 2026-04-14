# ============================================================
# auth_middleware.py — Verificación de tokens JWT de Supabase
# Soporta ES256 (nuevo sistema Supabase) y HS256 (legacy)
# ============================================================

import os
import jwt
import requests as http_requests
from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import lru_cache

SUPABASE_URL        = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_supabase_jwks() -> dict:
    """
    Descarga las claves públicas JWKS de Supabase (para ES256).
    Se cachea en memoria para no hacer un request en cada verificación.
    """
    try:
        url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        res = http_requests.get(url, timeout=5)
        res.raise_for_status()
        return res.json()
    except Exception:
        return {}


def verify_token(credentials: HTTPAuthorizationCredentials) -> dict:
    """
    Verifica el JWT emitido por Supabase Auth.
    Soporta tanto ES256 (nuevo) como HS256 (legacy).
    Retorna el payload si el token es válido.
    Lanza HTTPException 401 si no lo es.

    SEGURIDAD: verify_signature=False fue eliminado por completo.
    En cualquier entorno (dev o prod) se exige una firma válida.
    - ES256: requiere SUPABASE_URL para obtener JWKS.
    - HS256: requiere SUPABASE_JWT_SECRET.
    Si falta alguna variable de entorno, el endpoint falla con 500
    en lugar de aceptar tokens sin verificar.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="No autenticado — inicia sesión")

    token = credentials.credentials

    # ── Detectar algoritmo del token ────────────────────────
    try:
        header    = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "HS256")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    # ── ES256: verificar con clave pública JWKS ─────────────
    if algorithm == "ES256":
        if not SUPABASE_URL:
            # Sin SUPABASE_URL no podemos verificar la firma → rechazar siempre.
            # Agrega SUPABASE_URL a tus variables de entorno (dev y prod).
            raise HTTPException(
                status_code=500,
                detail="Configuración incompleta: falta SUPABASE_URL"
            )

        try:
            jwks       = get_supabase_jwks()
            kid        = header.get("kid")
            public_key = None
            for key_data in jwks.get("keys", []):
                if key_data.get("kid") == kid:
                    public_key = jwt.algorithms.ECAlgorithm.from_jwk(key_data)
                    break

            if not public_key:
                raise HTTPException(status_code=401, detail="Clave pública no encontrada")

            payload = jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                audience="authenticated",
            )
            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Sesión expirada — vuelve a iniciar sesión")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Token inválido")

    # ── HS256: verificar con JWT secret (legacy) ─────────────
    if not SUPABASE_JWT_SECRET:
        # Sin secret no podemos verificar la firma → rechazar siempre.
        # Agrega SUPABASE_JWT_SECRET a tus variables de entorno (dev y prod).
        raise HTTPException(
            status_code=500,
            detail="Configuración incompleta: falta SUPABASE_JWT_SECRET"
        )

    try:
        payload = jwt.decode(
            token,
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
