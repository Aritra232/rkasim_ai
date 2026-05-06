from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import logging
from typing import List

from com.mhire.app.services.verification.verification2 import FaceVerificationService
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
    prefix="/api/v1",
    tags=["NID and Face Verification"]
)

# Initialize the verification service
verification_service = FaceVerificationService()


@router.post("/nid_verification")
async def verify_identity(
    
    nid_card: UploadFile = File(..., description="NID card image"),
    face_photo: UploadFile = File(..., description="Face photo for verification"),
    confidence_threshold: int = Form(75, description="Confidence threshold (50-95)")
):
    """
    Verify identity by comparing a face photo with an NID card and extract NID information.
    
    - **face_photo**: Upload a clear, front-facing photo of the person
    - **nid_card**: Upload a clear photo of the NID card (supports multiple photos on card)
    - **confidence_threshold**: Minimum confidence score required for a positive match (50-95)
    
    Returns verification result with confidence score, match status, and extracted NID information.
    """
    
    # Validate confidence threshold
    if not 50 <= confidence_threshold <= 95:
        return JSONResponse(
            status_code=400,
            content={"message": "Confidence threshold must be between 50 and 95"}
        )
    
    # Check if API keys are configured
    if not verification_service.api_key or not verification_service.api_secret:
        return JSONResponse(
            status_code=500,
            content={"message": "Face++ API credentials not configured"}
        )
    
    # Validate file types
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
    
    if face_photo.content_type not in allowed_types:
        return JSONResponse(
            status_code=400,
            content={"message": f"Face photo must be JPEG or PNG. Got: {face_photo.content_type}"}
        )
    
    if nid_card.content_type not in allowed_types:
        return JSONResponse(
            status_code=400,
            content={"message": f"NID card must be JPEG or PNG. Got: {nid_card.content_type}"}
        )
    
    try:
        # Read uploaded files
        face_data = await face_photo.read()
        nid_data = await nid_card.read()
        
        # Validate file sizes (max 10MB each)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(face_data) > max_size:
            return JSONResponse(
                status_code=400,
                content={"message": "Face photo file size too large (max 10MB)"}
            )
        
        if len(nid_data) > max_size:
            return JSONResponse(
                status_code=400,
                content={"message": "NID card file size too large (max 10MB)"}
            )
        
        # Process images
        logger.info("Processing face photo...")
        processed_face_data = verification_service.process_uploaded_image(face_data)
        
        if processed_face_data is None:
            return JSONResponse(
                status_code=400,
                content={"message": "Failed to process face photo"}
            )
        
        logger.info("Processing NID card...")
        processed_nid_data = verification_service.process_uploaded_image(nid_data)
        
        if processed_nid_data is None:
            return JSONResponse(
                status_code=400,
                content={"message": "Failed to process NID card"}
            )
        
        # Extract NID information using OpenAI Vision API
        logger.info("Extracting NID information...")
        nid_extraction_result = verification_service.extract_nid_information(processed_nid_data)
        logger.info(f"NID extraction result: {nid_extraction_result}")
        
        if not nid_extraction_result.get('success', False):
            logger.warning(f"NID extraction failed: {nid_extraction_result.get('error', 'Unknown error')}")
            # Continue with verification even if extraction fails
        
        # Initialize DB manager for possible NID lookups and saves
        from com.mhire.app.database.db_manager import DBManager
        db_manager = DBManager()

        # Check if NID already exists in database
        nid_exists = False
        existing_user = None
        if nid_extraction_result.get('id_number'):
            nid_exists = await db_manager.check_nid_info_exists(nid_extraction_result['id_number'])
            if nid_exists:
                existing_user = await db_manager.get_nid_info_by_id_number(nid_extraction_result['id_number'])
                logger.info(f"NID already exists in database: {nid_extraction_result['id_number']}")

                # Convert ObjectId and datetime to string for JSON serialization
                if existing_user:
                    if '_id' in existing_user:
                        existing_user['_id'] = str(existing_user['_id'])
                    if 'created_at' in existing_user:
                        existing_user['created_at'] = str(existing_user['created_at'])

        # If NID exists, return existing user result without requiring face match
        if nid_exists:
            response_data = {
                'nid_extraction': nid_extraction_result,
                'nid_exists': nid_exists,
                'existing_user': existing_user,
                'message': "NID already exists in the system. Face match is not required for existing records."
            }
            return response_data

        # Perform face verification for new NID registrations
        logger.info("Comparing faces...")
        verification_result = verification_service.compare_face_with_nid(
            processed_face_data,
            processed_nid_data,
            confidence_threshold
        )

        # Prepare response data for new NID verification
        response_data = {
            'verification': verification_result,
            'nid_extraction': nid_extraction_result,
            'nid_exists': nid_exists,
            'face_match': verification_result.get('match', False)
        }

        # Handle error cases with clean error messages
        if not verification_result.get('success', False):
            error_message = verification_result.get('error', 'Verification failed')

            if "No face detected in the face photo and No face detected in the NID card" in error_message:
                response_data['message'] = "No face found in both the photo and NID card"
            elif "No face detected in the face photo" in error_message:
                response_data['message'] = "No face found in the photo"
            elif "No face detected in the NID card" in error_message:
                response_data['message'] = "No face found in the NID card"
            elif "Multiple faces detected in face photo" in error_message:
                response_data['message'] = "Multiple faces detected in face photo. Please use image with single face"
            else:
                response_data['message'] = error_message

            return JSONResponse(
                status_code=400,
                content=response_data
            )

        # If the face did not match for a new NID, reject the verification
        if not verification_result.get('match', False):
            response_data['message'] = "Face did not match the NID card"
            return JSONResponse(
                status_code=400,
                content=response_data
            )

        # Save NID information if extraction succeeded for a new NID
        can_save_nid = (
            nid_extraction_result.get('success', False) and 
            nid_extraction_result.get('id_number') and 
            not nid_exists
        )

        if can_save_nid:
            logger.info("Saving new NID information to database...")
            saved_user_id = await db_manager.save_nid_information(nid_extraction_result)
            response_data['saved_user_id'] = saved_user_id
            logger.info(f"NID information saved successfully with ID: {saved_user_id}")
        else:
            logger.info(
                f"Skipping NID save: success={nid_extraction_result.get('success', False)}, "
                f"id_number={nid_extraction_result.get('id_number')}, nid_exists={nid_exists}"
            )

        response_data['message'] = "Face matched with NID and new NID verification passed"
        return response_data
        
    except Exception as e:
        logger.error(f"Unexpected error during verification: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"An unexpected error occurred: {str(e)}"}
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