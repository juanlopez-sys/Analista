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
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="No autenticado — inicia sesión")

    token = credentials.credentials

    # ── Detectar algoritmo del token ────────────────────────
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "HS256")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    # ── ES256: verificar con clave pública JWKS ─────────────
    if algorithm == "ES256":
        if not SUPABASE_URL:
            # Sin SUPABASE_URL no podemos obtener JWKS — verificar sin firma
            # Solo en desarrollo. En producción agrega SUPABASE_URL a env vars.
            try:
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False},
                    algorithms=["ES256"],
                )
                _check_expiry(payload)
                return payload
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=401, detail="Token inválido")

        try:
            jwks = get_supabase_jwks()
            kid  = header.get("kid")
            # Buscar la clave correcta por kid
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
        if os.getenv("RENDER"):
            raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET no configurado")
        # Desarrollo local sin secret — no verificar firma
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception:
            raise HTTPException(status_code=401, detail="Token inválido")

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


def _check_expiry(payload: dict):
    """Verifica manualmente que el token no esté expirado."""
    import time
    exp = payload.get("exp")
    if exp and time.time() > exp:
        raise HTTPException(status_code=401, detail="Sesión expirada — vuelve a iniciar sesión")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = None
) -> dict:
    """
    Dependencia de FastAPI para proteger endpoints.
    Uso: user = Depends(get_current_user)
    """
    return verify_token(credentials)
