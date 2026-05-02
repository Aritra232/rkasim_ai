import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from fastapi import HTTPException

from com.mhire.app.database.db_manager import DBManager
from com.mhire.app.services.verification_system.face_verification.face_verification_schema import FaceVerificationMatch, ErrorResponse, VerificationResponse
from com.mhire.app.services.verification_system.api_manager.faceplusplus_manager import FacePlusPlusManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceVerification:
    def __init__(self):
        self.confidence_threshold = 90.0  # 88% confidence threshold
        self.min_face_quality = 70.0  # Minimum face quality threshold
        self.fpp_manager = FacePlusPlusManager()
        self.db_manager = DBManager()

    def _validate_face_attributes(self, attributes: dict) -> Tuple[bool, str]:
        """Validate face attributes to ensure it's a human face"""
        if not attributes:
            return False, "No face attributes detected"
            
        # Check face quality
        face_quality = attributes.get('facequality', {}).get('value', 0)
        if face_quality < self.min_face_quality:
            # return False, f"Face quality too low ({face_quality}). Please provide a clearer photo."
            return False, f"No face attributes detected"
            
        # Validate presence of human attributes
        if not attributes.get('gender') or not attributes.get('age'):
            return False, "Unable to detect human face characteristics"
            
        return True, "Valid human face detected"

    async def search_similar_faces(self, face_token: str) -> List[FaceVerificationMatch]:
        """Search for similar faces across all FaceSets"""
        try:
            matches = []
            facesets = await self.db_manager.get_all_stored_faces()
            
            for faceset_id, stored_tokens in facesets.items():
                if not stored_tokens:  # Skip empty facesets
                    continue
                    
                try:
                    results = await self.fpp_manager.search_faces(face_token, faceset_id)
                    
                    # Process matches above threshold
                    for result in results:
                        confidence = float(result.get('confidence', 0))
                        if confidence >= self.confidence_threshold:
                            matches.append(FaceVerificationMatch(
                                confidence=confidence,
                                face_token=result.get('face_token', '')
                            ))
                except Exception as e:
                    logger.warning(f"Error searching FaceSet {faceset_id}: {str(e)}")
                    continue
            
            return sorted(matches, key=lambda x: x.confidence, reverse=True)
            
        except Exception as e:
            logger.error(f"Error during face search: {str(e)}")
            error = ErrorResponse(status_code=500, detail=f"Error during face search: {str(e)}")
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def save_face_data(self, face_token: str) -> bool:
        """Save face token and add to appropriate FaceSet"""
        try:
            faceset_info = await self.db_manager.find_available_faceset()
            faceset_id = None
            
            if faceset_info:
                faceset_id = faceset_info[0]
                details = await self.fpp_manager.get_faceset_detail(faceset_id)
                if not details or 'error_message' in details:
                    logger.warning(f"Faceset {faceset_id} exists in database but not in Face++ API. Creating new faceset.")
                    faceset_id = None
            
            if not faceset_id:
                faceset_id = await self.fpp_manager.create_new_faceset()
                if not faceset_id:
                    error = ErrorResponse(status_code=500, detail="Failed to create new FaceSet in Face++ API")
                    raise HTTPException(status_code=error.status_code, detail=error.dict())

            added = await self.fpp_manager.add_face_to_faceset(face_token, faceset_id)
            if not added:
                error = ErrorResponse(status_code=500, detail=f"Failed to add face to FaceSet {faceset_id} in Face++ API")
                raise HTTPException(status_code=error.status_code, detail=error.dict())

            saved = await self.db_manager.save_face_token(face_token, faceset_id)
            if not saved:
                error = ErrorResponse(status_code=500, detail="Failed to save face token to database")
                raise HTTPException(status_code=error.status_code, detail=error.dict())

            details = await self.fpp_manager.get_faceset_detail(faceset_id)
            if details and 'face_count' in details:
                await self.db_manager.update_faceset_count(faceset_id, details['face_count'])
            
            logger.info(f"Successfully saved face token and added to FaceSet {faceset_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving face data: {str(e)}")
            error = ErrorResponse(status_code=500, detail=f"Error saving face data: {str(e)}")
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def verify_face(self, image_data: bytes) -> Dict:
        """Main verification flow with human face validation"""
        try:
            # Get face token and attributes
            face_token, attributes = await self.fpp_manager.detect_face(image_data)
            
            if not face_token:
                return VerificationResponse(
                    status="error",
                    message="No face detected in image",
                    is_duplicate=False,
                    face_token=None,
                    confidence=None,
                    matches=None
                ).dict()

            # Validate human face
            is_valid, message = self._validate_face_attributes(attributes)
            if not is_valid:
                return VerificationResponse(
                    status="error",
                    message=message,
                    is_duplicate=False,
                    face_token=None,
                    confidence=None,
                    matches=None
                ).dict()

            logger.info(f"Valid human face detected with token: {face_token}")
            
            # Search for similar faces
            matches = await self.search_similar_faces(face_token)
            
            if matches:
                best_match = matches[0]
                return VerificationResponse(
                    status="duplicate_found",
                    message="Potential duplicate face detected",
                    is_duplicate=True,
                    face_token=face_token,
                    confidence=best_match.confidence,
                    matches=matches
                ).dict()
            
            # No matches found, save new face
            if not await self.save_face_data(face_token):
                return VerificationResponse(
                    status="error",
                    message="Failed to save face data",
                    is_duplicate=False,
                    face_token=None,
                    confidence=None,
                    matches=None
                ).dict()

            return VerificationResponse(
                status="success",
                message="New face registered successfully",
                is_duplicate=False,
                face_token=face_token,
                confidence=None,
                matches=None
            ).dict()
            
        except Exception as e:
            logger.error(f"Error in face verification: {str(e)}")
            return VerificationResponse(
                status="error",
                message=str(e),
                is_duplicate=False,
                face_token=None,
                confidence=None,
                matches=None
            ).dict()
        try:
            # Get face token and attributes
            face_token, attributes = await self.fpp_manager.detect_face(image_data)
            
            if not face_token:
                error = ErrorResponse(status_code=400, detail="No face detected in image")
                raise HTTPException(status_code=error.status_code, detail=error.dict())

            # Validate human face
            is_valid, message = self._validate_face_attributes(attributes)
            if not is_valid:
                error = ErrorResponse(status_code=400, detail=message)
                raise HTTPException(status_code=error.status_code, detail=error.dict())

            logger.info(f"Valid human face detected with token: {face_token}")
            
            matches = await self.search_similar_faces(face_token)
            
            if matches:
                best_match = matches[0]
                return VerificationResponse(
                    status="duplicate_found",
                    message="Potential duplicate face detected",
                    is_duplicate=True,
                    face_token=face_token,
                    confidence=best_match.confidence,
                    matches=matches
                ).dict()
            
            if not await self.save_face_data(face_token):
                error = ErrorResponse(status_code=500, detail="Failed to save face data")
                raise HTTPException(status_code=error.status_code, detail=error.dict())

            return VerificationResponse(
                status="success",
                message="New face found and token saved successfully",
                is_duplicate=False,
                face_token=face_token
            ).dict()
            
        except Exception as e:
            logger.error(f"Error in face verification: {str(e)}")
            error = ErrorResponse(status_code=500, detail=str(e))
            raise HTTPException(status_code=error.status_code, detail=error.dict())