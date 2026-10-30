import os
from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import PyJWTError, ExpiredSignatureError, InvalidSignatureError
from dotenv import load_dotenv
from .models import CompanyUser, CompanyUserRole, Role

load_dotenv()

SECRETO = os.environ.get("JWT_SECRET")
if not SECRETO:
    raise RuntimeError("Falta la variable de entorno JWT_SECRET")

ALGORITMO = "HS256"
MINUTOS_VIGENCIA = 30

def crear_token(company_user_id: int, company_id: int) -> str:
    ahora = datetime.now(timezone.utc)
    datos = {
        "companyUserId": company_user_id,
        "companyId": company_id,
        "exp": ahora + timedelta(minutes=MINUTOS_VIGENCIA),
    }
    return jwt.encode(datos, SECRETO, algorithm=ALGORITMO)

def leer_actor(db_session, info):
    request = info.context.get("request")
    if not request:
        raise Exception("Contexto de petición HTTP no disponible en GraphQL.")
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise Exception("Acceso denegado: Token no proporcionado o formato inválido.")
    
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, SECRETO, algorithms=[ALGORITMO])
    except ExpiredSignatureError:
        raise Exception("Token expirado. Por favor, inicia sesión nuevamente.")
    except InvalidSignatureError:
        raise Exception("Firma del token inválida.")
    except PyJWTError as e:
        raise Exception(f"Token inválido: {str(e)}")
    
    company_user_id = payload.get("companyUserId")
    company_id = payload.get("companyId")
    
    if not company_user_id or not company_id:
        raise Exception("Token malformado: Faltan datos esenciales del usuario.")
    
    company_user = db_session.query(CompanyUser).filter_by(
        id=company_user_id,
        company_id=company_id,
        is_active=True
    ).first()
    
    if not company_user:
        raise Exception("El usuario no cuenta con una membresía activa en esta empresa.")
        
    user_role = db_session.query(CompanyUserRole).filter_by(
        company_user_id=company_user.id,
        is_active=True
    ).first()
    
    if not user_role:
        raise Exception("El usuario no tiene un rol activo asignado.")
        
    return {
        "company_user": company_user,
        "company_id": company_id,
        "role_id": user_role.role_id,
        "role_code": user_role.role.code if user_role.role else None
    }