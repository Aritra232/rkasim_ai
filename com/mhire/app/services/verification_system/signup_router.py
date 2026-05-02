import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
import uuid

from com.mhire.app.services.verification_system.face_verification.face_verification import FaceVerification
from com.mhire.app.services.verification_system.face_verification.face_verification_schema import SignupResponse
from com.mhire.app.database.db_manager import DBManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["User Signup"],
    responses={
        400: {"description": "Bad request"},
        409: {"description": "Conflict - Duplicate NID"},
        500: {"description": "Internal server error"}
    }
)

db_manager = DBManager()
face_verification = FaceVerification()


@router.post("/signup", response_model=SignupResponse)
async def signup_user(
    nid: str = Form(..., description="National ID number"),
    face_photo: UploadFile = File(..., description="Face photo for verification"),
    email: Optional[str] = Form(None, description="User email"),
    phone: Optional[str] = Form(None, description="User phone"),
    name: Optional[str] = Form(None, description="User full name")
):
    """
    Complete user signup with NID verification and face registration.
    
    Process:
    1. Check if NID already exists (prevent duplicates)
    2. Validate face and detect face token
    3. Check if face is duplicate (prevent duplicate faces)
    4. Register user with both NID and face token
    
    Returns signup result with user ID and verification status.
    """
    
    # Validate NID format (basic check - adjust based on your requirements)
    if not nid or len(nid.strip()) < 5:
        return SignupResponse(
            status="error",
            message="Invalid NID format",
            success=False,
            error="NID must be at least 5 characters"
        )
    
    nid = nid.strip()
    
    try:
        # Step 1: Check if NID already exists
        logger.info(f"Checking if NID {nid} already exists...")
        nid_exists = await db_manager.check_nid_exists(nid)
        
        if nid_exists:
            logger.warning(f"NID {nid} already registered")
            return SignupResponse(
                status="duplicate_nid",
                message="This NID has already been registered",
                success=False,
                error="Duplicate NID - User already exists with this NID"
            )
        
        # Step 2: Validate face photo
        if not face_photo.content_type.startswith('image/'):
            return SignupResponse(
                status="error",
                message="Invalid file type",
                success=False,
                error="Face photo must be an image file"
            )
        
        face_data = await face_photo.read()
        if not face_data:
            return SignupResponse(
                status="error",
                message="Empty face photo",
                success=False,
                error="Face photo file is empty"
            )
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024
        if len(face_data) > max_size:
            return SignupResponse(
                status="error",
                message="File too large",
                success=False,
                error="Face photo must be less than 10MB"
            )
        
        # Step 3: Process face and check for duplicates
        logger.info(f"Processing face for NID {nid}...")
        result = await face_verification.verify_face(face_data)
        
        # Check if face verification failed
        if result.get("status") == "error":
            logger.warning(f"Face verification error for NID {nid}: {result.get('message')}")
            return SignupResponse(
                status="error",
                message=result.get("message", "Face verification failed"),
                success=False,
                error=result.get("message")
            )
        
        # Check if face is duplicate
        if result.get("is_duplicate"):
            logger.warning(f"Duplicate face detected for NID {nid}")
            return SignupResponse(
                status="duplicate_face",
                message="This face has already been registered",
                success=False,
                error="Duplicate face - This person has already signed up"
            )
        
        # Step 4: Save user with NID and face token
        face_token = result.get("face_token")
        faceset_id = None
        
        # Extract faceset_id from additional_info if available
        if result.get("additional_info") and "faceset_id" in result.get("additional_info"):
            faceset_id = result.get("additional_info")["faceset_id"]
        
        # Prepare user data
        user_data = {
            "email": email,
            "phone": phone,
            "name": name
        }
        # Remove None values
        user_data = {k: v for k, v in user_data.items() if v is not None}
        
        logger.info(f"Saving user with NID {nid} and face token...")
        user_id = await db_manager.save_user_with_nid(
            nid=nid,
            face_token=face_token,
            faceset_id=faceset_id or "default",
            user_data=user_data
        )
        
        if not user_id:
            logger.error(f"Failed to save user with NID {nid}")
            return SignupResponse(
                status="error",
                message="Failed to save user",
                success=False,
                error="Database error - could not save user"
            )
        
        logger.info(f"User signup successful - User ID: {user_id}, NID: {nid}")
        return SignupResponse(
            status="success",
            message="User registered successfully",
            success=True,
            user_id=user_id,
            face_token=face_token,
            nid=nid
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during signup for NID {nid}: {str(e)}")
        return SignupResponse(
            status="error",
            message="An unexpected error occurred during signup",
            success=False,
            error=str(e)
        )


@router.post("/check-nid")
async def check_nid_availability(nid: str = Form(..., description="NID to check")):
    """
    Check if an NID is already registered (before signup).
    
    Returns availability status.
    """
    
    if not nid or len(nid.strip()) < 5:
        return {
            "status": "invalid",
            "available": False,
            "message": "Invalid NID format"
        }
    
    try:
        nid_exists = await db_manager.check_nid_exists(nid.strip())
        
        return {
            "status": "available" if not nid_exists else "duplicate",
            "available": not nid_exists,
            "message": "NID is available" if not nid_exists else "NID is already registered"
        }
    except Exception as e:
        logger.error(f"Error checking NID availability: {str(e)}")
        return {
            "status": "error",
            "available": False,
            "message": f"Error checking NID: {str(e)}"
        }


@router.get("/user/{nid}")
async def get_user_by_nid(nid: str):
    """
    Retrieve user information by NID (for verification purposes).
    
    Note: In production, add authentication/authorization checks.
    """
    
    try:
        user = await db_manager.get_user_by_nid(nid)
        
        if not user:
            return {
                "status": "not_found",
                "message": "User not found"
            }
        
        # Remove sensitive data before returning
        user_response = {
            "user_id": str(user.get("_id")),
            "nid": user.get("nid"),
            "name": user.get("name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "created_at": user.get("created_at"),
            "status": user.get("status")
        }
        
        return {
            "status": "found",
            "user": user_response
        }
    except Exception as e:
        logger.error(f"Error retrieving user by NID: {str(e)}")
        return {
            "status": "error",
            "message": f"Error retrieving user: {str(e)}"
        }
