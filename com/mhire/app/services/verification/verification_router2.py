from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import logging
from typing import List

from com.mhire.app.services.verification.verification import FaceVerificationService
from com.mhire.app.services.verification.verification_schema import (
    VerificationResult, 
    HealthCheck, 
    BatchVerificationResponse, 
    APIInfo,
    BatchVerificationResult
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/api/v1/verification",
    tags=["Biometric Verification"]
)

# Initialize the verification service
verification_service = FaceVerificationService()


# @router.get("/", response_model=HealthCheck)
# async def root():
#     """Root endpoint - Health check"""
#     return HealthCheck(
#         status="healthy",
#         message="Face-NID Verification API is running"
#     )


# @router.get("/health", response_model=HealthCheck)
# async def health_check():
#     """Health check endpoint"""
#     # Check if API keys are configured
#     if not verification_service.api_key or not verification_service.api_secret:
#         return HealthCheck(
#             status="unhealthy",
#             message="Face++ API credentials not configured"
#         )
    
#     return HealthCheck(
#         status="healthy",
#         message="API is ready for face verification"
#     )


@router.post("/verify", response_model=VerificationResult)
async def verify_identity(
    nid_card: UploadFile = File(..., description="NID card image"),
    face_photo: UploadFile = File(..., description="Face photo for verification"),
    confidence_threshold: int = Form(75, description="Confidence threshold (50-95)")
):
    """
    Verify identity by comparing a face photo with an NID card.
    
    - **face_photo**: Upload a clear, front-facing photo of the person
    - **nid_card**: Upload a clear photo of the NID card (supports multiple photos on card)
    - **confidence_threshold**: Minimum confidence score required for a positive match (50-95)
    
    Returns verification result with confidence score and match status.
    """
    
    # Validate confidence threshold
    if not 50 <= confidence_threshold <= 95:
        raise HTTPException(
            status_code=400,
            detail="Confidence threshold must be between 50 and 95"
        )
    
    # Check if API keys are configured
    if not verification_service.api_key or not verification_service.api_secret:
        raise HTTPException(
            status_code=500,
            detail="Face++ API credentials not configured"
        )
    
    # Validate file types
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
    
    if face_photo.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Face photo must be JPEG or PNG. Got: {face_photo.content_type}"
        )
    
    if nid_card.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"NID card must be JPEG or PNG. Got: {nid_card.content_type}"
        )
    
    try:
        # Read uploaded files
        face_data = await face_photo.read()
        nid_data = await nid_card.read()
        
        # Validate file sizes (max 10MB each)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(face_data) > max_size:
            raise HTTPException(
                status_code=400,
                detail="Face photo file size too large (max 10MB)"
            )
        
        if len(nid_data) > max_size:
            raise HTTPException(
                status_code=400,
                detail="NID card file size too large (max 10MB)"
            )
        
        # Process images
        logger.info("Processing face photo...")
        processed_face_data = verification_service.process_uploaded_image(face_data)
        
        if processed_face_data is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to process face photo"
            )
        
        logger.info("Processing NID card...")
        processed_nid_data = verification_service.process_uploaded_image(nid_data)
        
        if processed_nid_data is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to process NID card"
            )
        
        # Perform verification
        logger.info("Comparing faces...")
        result = verification_service.compare_face_with_nid(
            processed_face_data,
            processed_nid_data,
            confidence_threshold
        )
        
        # Return result
        return VerificationResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during verification: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )


# @router.post("/verify-batch", response_model=BatchVerificationResponse)
# async def verify_batch(
#     files: List[UploadFile] = File(..., description="List of files: [face1, nid1, face2, nid2, ...]"),
#     confidence_threshold: int = Form(75, description="Confidence threshold (50-95)")
# ):
#     """
#     Batch verification of multiple face-NID pairs.
    
#     Upload files in pairs: face1, nid1, face2, nid2, etc.
#     Returns a list of verification results.
#     """
    
#     # Validate confidence threshold
#     if not 50 <= confidence_threshold <= 95:
#         raise HTTPException(
#             status_code=400,
#             detail="Confidence threshold must be between 50 and 95"
#         )
    
#     # Check if API keys are configured
#     if not verification_service.api_key or not verification_service.api_secret:
#         raise HTTPException(
#             status_code=500,
#             detail="Face++ API credentials not configured"
#         )
    
#     # Validate file count (must be even)
#     if len(files) % 2 != 0:
#         raise HTTPException(
#             status_code=400,
#             detail="Files must be uploaded in pairs (face, nid, face, nid, ...)"
#         )
    
#     results = []
    
#     try:
#         # Process files in pairs
#         for i in range(0, len(files), 2):
#             face_file = files[i]
#             nid_file = files[i + 1]
            
#             logger.info(f"Processing pair {i//2 + 1}: {face_file.filename} and {nid_file.filename}")
            
#             # Read files
#             face_data = await face_file.read()
#             nid_data = await nid_file.read()
            
#             # Process images
#             processed_face_data = verification_service.process_uploaded_image(face_data)
#             processed_nid_data = verification_service.process_uploaded_image(nid_data)
            
#             if processed_face_data is None or processed_nid_data is None:
#                 result_data = {
#                     'success': False,
#                     'error': f"Failed to process images for pair {i//2 + 1}",
#                     'match': False,
#                     'confidence': 0,
#                     'threshold_used': confidence_threshold,
#                     'message': f"Failed to process images for pair {i//2 + 1}",
#                     'pair_index': i//2 + 1,
#                     'face_filename': face_file.filename,
#                     'nid_filename': nid_file.filename
#                 }
#                 results.append(BatchVerificationResult(**result_data))
#                 continue
            
#             # Perform verification
#             result = verification_service.compare_face_with_nid(
#                 processed_face_data,
#                 processed_nid_data,
#                 confidence_threshold
#             )
            
#             # Add metadata and convert to BatchVerificationResult
#             result_data = {
#                 **result,
#                 'pair_index': i//2 + 1,
#                 'face_filename': face_file.filename,
#                 'nid_filename': nid_file.filename
#             }
            
#             results.append(BatchVerificationResult(**result_data))
        
#         return BatchVerificationResponse(results=results, total_pairs=len(results))
        
#     except Exception as e:
#         logger.error(f"Error in batch verification: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Batch verification failed: {str(e)}"
#         )


# @router.get("/api-info", response_model=APIInfo)
# async def api_info():
#     """Get API information and usage guidelines"""
#     return APIInfo(
#         api_name="Face-NID Verification API",
#         version="1.0.0",
#         description="Verify identity by comparing face photos with NID cards",
#         features=[
#             "Single face-NID verification",
#             "Batch verification",
#             "Automatic image resizing",
#             "Multiple face handling in NID cards",
#             "Quality analysis"
#         ],
#         supported_formats=["JPEG", "PNG"],
#         max_file_size="10MB",
#         confidence_threshold_range="50-95%",
#         endpoints={
#             "/verify": "Single verification",
#             "/verify-batch": "Batch verification",
#             "/health": "Health check",
#             "/api-info": "API information"
#         }
#     )