from fastapi import APIRouter, HTTPException
from app.schemas import AuthRequest, AuthResponse

router = APIRouter()

@router.post("/auth", response_model=AuthResponse)
async def authenticate(auth: AuthRequest):
    # Mock: treat token as email for demo; in real use, validate token and extract email
    if "@" in auth.token:
        return AuthResponse(email=auth.token, valid=True)
    return AuthResponse(email="invalid@example.com", valid=False) 