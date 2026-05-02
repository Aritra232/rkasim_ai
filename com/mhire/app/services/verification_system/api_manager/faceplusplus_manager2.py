import logging
import uuid
import time
from typing import Dict, List, Optional, Tuple
import requests
import json

from fastapi import HTTPException

from com.mhire.app.config.config import Config
from com.mhire.app.services.verification_system.face_verification.face_verification_schema import ErrorResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FacePlusPlusManager:
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.api_key
        self.api_secret = self.config.api_secret
        self.detect_url = self.config.fpp_detect
        self.search_url = self.config.fpp_search
        self.create_url = self.config.fpp_create
        self.add_url = self.config.fpp_add
        self.get_detail_url = self.config.fpp_get_detail
        
        # Rate limiting settings
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.last_request_time = 0

        if not all([self.api_key, self.api_secret]):
            error = ErrorResponse(status_code=500, detail="Face++ API credentials not configured")
            raise HTTPException(status_code=error.status_code, detail=error.dict())

        self.detect_params = {
            'return_attributes': 'gender,age,ethnicity,facequality'  # Add face quality check
        }

    def _get_base_params(self) -> Dict[str, str]:
        """Get base parameters required for all API calls"""
        return {
            'api_key': self.api_key,
            'api_secret': self.api_secret
        }

    def _handle_rate_limit(self):
        """Implement rate limiting with delay between requests"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.retry_delay:
            sleep_time = self.retry_delay - time_since_last_request
            logger.info(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()

    def _make_request(self, url: str, data: Dict, files: Dict = None, operation: str = "") -> Dict:
        """Make request to Face++ API with retry logic and proper error handling"""
        for attempt in range(self.max_retries):
            try:
                # Apply rate limiting
                self._handle_rate_limit()
                
                safe_data = {k: v for k, v in data.items() if k not in ['api_key', 'api_secret']}
                logger.info(f"Making {operation} request to Face++ API with data: {json.dumps(safe_data)}")
                
                response = requests.post(url, data=data, files=files)
                
                try:
                    result = response.json()
                    
                    # Check for rate limit error
                    if 'error_message' in result and 'CONCURRENCY_LIMIT_EXCEEDED' in result['error_message']:
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (attempt + 1)  # Exponential backoff
                            logger.warning(f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                            time.sleep(wait_time)
                            continue
                    
                    if response.status_code != 200:
                        error = ErrorResponse(
                            status_code=response.status_code,
                            detail=f"{operation} failed: {json.dumps(result)}"
                        )
                        raise HTTPException(status_code=error.status_code, detail=error.dict())
                    
                    if 'error_message' in result:
                        error = ErrorResponse(
                            status_code=400,
                            detail=f"{operation} failed: {result['error_message']}"
                        )
                        raise HTTPException(status_code=error.status_code, detail=error.dict())
                    
                    return result
                    
                except json.JSONDecodeError:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    error = ErrorResponse(
                        status_code=500,
                        detail=f"Invalid response from Face++ API in {operation}"
                    )
                    raise HTTPException(status_code=error.status_code, detail=error.dict())
                    
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                error = ErrorResponse(
                    status_code=503,
                    detail=f"API request failed in {operation}: {str(e)}"
                )
                raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def create_new_faceset(self) -> str:
        """Create a new FaceSet with retry logic"""
        try:
            new_outer_id = f"faceset_{uuid.uuid4().hex[:8]}"
            data = {
                **self._get_base_params(),
                'outer_id': new_outer_id,
                'display_name': new_outer_id,
                'tags': 'face_verification'
            }
            
            result = self._make_request(
                self.create_url,
                data=data,
                operation="create_faceset"
            )
            
            if result and result.get('faceset_token'):
                logger.info(f"Successfully created new FaceSet: {new_outer_id}")
                return new_outer_id
            error = ErrorResponse(
                status_code=500,
                detail="Failed to create FaceSet: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Failed to create FaceSet: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def add_face_to_faceset(self, face_token: str, outer_id: str) -> bool:
        """Add a face token to a specific FaceSet with retry logic"""
        try:
            data = {
                **self._get_base_params(),
                'face_tokens': face_token,
                'outer_id': outer_id
            }
            
            result = self._make_request(
                self.add_url,
                data=data,
                operation="add_face"
            )
            
            if result and 'face_added' in result:
                logger.info(f"Successfully added face to FaceSet {outer_id}")
                return True
            error = ErrorResponse(
                status_code=500,
                detail="Failed to add face: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Failed to add face to FaceSet: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def detect_face(self, image_data: bytes) -> Tuple[Optional[str], Optional[dict]]:
        """Detect face and get face token with attributes from Face++ API"""
        try:
            files = {
                'image_file': ('image.jpg', image_data, 'image/jpeg')
            }
            
            # Add detect parameters to base params
            data = {
                **self._get_base_params(),
                **self.detect_params
            }
            
            result = self._make_request(
                self.detect_url,
                data=data,
                files=files,
                operation="detect_face"
            )
            
            if not result.get('faces'):
                logger.info("No face detected in the provided image")
                return None, None
                
            face = result['faces'][0]
            face_token = face['face_token']
            attributes = face.get('attributes', {})
            
            # Check face quality
            face_quality = attributes.get('facequality', {}).get('value', 0)
            
            logger.info(f"Face detected with token: {face_token}, quality: {face_quality}")
            return face_token, attributes
            
        except Exception as e:
            logger.error(f"Face detection failed: {str(e)}")
            return None, None

    async def search_faces(self, face_token: str, outer_id: str, return_count: int = 5) -> List[Dict]:
        """Search for similar faces in a specific FaceSet with retry logic"""
        try:
            data = {
                **self._get_base_params(),
                'face_token': face_token,
                'outer_id': outer_id,
                'return_result_count': return_count
            }
            
            result = self._make_request(
                self.search_url,
                data=data,
                operation="search_faces"
            )
            
            if result and 'results' in result:
                logger.info(f"Search found {len(result['results'])} matches in FaceSet {outer_id}")
                return result['results']
            error = ErrorResponse(
                status_code=500,
                detail="Face search failed: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Face search failed: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def get_faceset_detail(self, outer_id: str) -> Dict:
        """Get details of a FaceSet with retry logic"""
        try:
            data = {
                **self._get_base_params(),
                'outer_id': outer_id
            }
            
            result = self._make_request(
                self.get_detail_url,
                data=data,
                operation="get_faceset_detail"
            )
            
            if result and 'face_count' in result:
                logger.info(f"Got details for FaceSet {outer_id}: {result['face_count']} faces")
                return result
            error = ErrorResponse(
                status_code=500,
                detail="Failed to get FaceSet details: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Failed to get FaceSet details: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())