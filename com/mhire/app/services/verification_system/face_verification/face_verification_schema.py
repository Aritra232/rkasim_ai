from pydantic import BaseModel
from typing import Optional, List

class FaceVerificationMatch(BaseModel):
    confidence: float
    face_token: str

class VerificationResponse(BaseModel):
    status: str
    message: str
    confidence: Optional[float] = None
    face_token: Optional[str] = None
    is_duplicate: bool = False
    matches: Optional[List[FaceVerificationMatch]] = None

class SignupRequest(BaseModel):
    nid: str
    face_photo: Optional[str] = None  # Base64 encoded or file reference

class SignupResponse(BaseModel):
    status: str
    message: str
    success: bool
    user_id: Optional[str] = None
    face_token: Optional[str] = None
    nid: Optional[str] = None
    error: Optional[str] = None

class ErrorResponse(BaseModel):
    """Standard error response model"""
    status_code: int
    detail: str
    error_type: Optional[str] = None  # For categorizing errors
    timestamp: Optional[str] = None    # For error tracking
