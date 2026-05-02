import requests
import json
from PIL import Image
import io
import logging
from typing import Optional, Tuple, Dict, Any
from com.mhire.app.config.config import Config
import base64
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize config
config = Config()
API_KEY = config.api_key
API_SECRET = config.api_secret


class FaceVerificationService:
    """Service class for face verification operations using Face++ API."""
    
    def __init__(self):
        self.api_key = API_KEY
        self.api_secret = API_SECRET
        self.compare_url = 'https://api-us.faceplusplus.com/facepp/v3/compare'
        self.detect_url = 'https://api-us.faceplusplus.com/facepp/v3/detect'
        self.ocr_url = 'https://api-us.faceplusplus.com/imagepp/v1/recognizetext'
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_vision_url = "https://api.openai.com/v1/chat/completions"
    
    def resize_image_if_needed(self, image_data: bytes, max_size_mb: int = 2, max_dimension: int = 1024) -> bytes:
        """
        Resize image if it's too large for Face++ API.
        
        Args:
            image_data (bytes): Image data
            max_size_mb (int): Maximum file size in MB
            max_dimension (int): Maximum width/height in pixels
        
        Returns:
            bytes: Resized image data
        """
        try:
            # Check file size
            file_size_mb = len(image_data) / (1024 * 1024)
            
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Check if resizing is needed
                width, height = img.size
                needs_resize = (file_size_mb > max_size_mb or 
                              width > max_dimension or 
                              height > max_dimension)
                
                if needs_resize:
                    # Calculate new dimensions while maintaining aspect ratio
                    if width > height:
                        new_width = min(width, max_dimension)
                        new_height = int((height * new_width) / width)
                    else:
                        new_height = min(height, max_dimension)
                        new_width = int((width * new_height) / height)
                    
                    # Resize image
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")
                
                # Save to bytes with optimized quality
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=85, optimize=True)
                img_byte_arr.seek(0)
                
                return img_byte_arr.getvalue()
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return image_data  # Return original data as fallback
    
    def get_largest_face(self, faces_list: list) -> Optional[dict]:
        """
        Get the largest face from a list of detected faces.
        This helps handle NID cards with multiple photos of the same person.
        
        Args:
            faces_list (list): List of face objects from Face++ API
        
        Returns:
            dict: The largest face object
        """
        if not faces_list:
            return None
        
        largest_face = None
        max_area = 0
        
        for face in faces_list:
            # Calculate face area using face rectangle
            face_rect = face.get('face_rectangle', {})
            width = face_rect.get('width', 0)
            height = face_rect.get('height', 0)
            area = width * height
            
            if area > max_area:
                max_area = area
                largest_face = face
        
        return largest_face
    
    def compare_face_with_nid(self, face_image_data: bytes, nid_image_data: bytes, confidence_threshold: int = 80) -> dict:
        """
        Compare a face photo with an NID card photo to verify identity match.
        Now handles multiple faces in NID cards by selecting the largest face.
        
        Args:
            face_image_data (bytes): Face image data
            nid_image_data (bytes): NID image data
            confidence_threshold (int): Minimum confidence score for a match (default: 80)
        
        Returns:
            dict: Result containing match status, confidence score, and details
        """
        
        try:
            # Prepare files for API
            files = {
                'image_file1': ('face.jpg', face_image_data, 'image/jpeg'),
                'image_file2': ('nid.jpg', nid_image_data, 'image/jpeg')
            }
            
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret
            }
            
            # Make the API request
            response = requests.post(self.compare_url, files=files, data=data)
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error processing images: {str(e)}",
                'match': False,
                'confidence': 0
            }
        
        # Check if the API call was successful
        if response.status_code != 200:
            return {
                'success': False,
                'error': f"API request failed with status code {response.status_code}: {response.text}",
                'match': False,
                'confidence': 0
            }
        
        try:
            result = response.json()
        except requests.exceptions.JSONDecodeError:
            return {
                'success': False,
                'error': "Unable to parse API response",
                'match': False,
                'confidence': 0
            }
        
        # Check for API errors
        if 'error_message' in result:
            return {
                'success': False,
                'error': f"Face++ API Error: {result['error_message']}",
                'match': False,
                'confidence': 0
            }
        
        # Check if faces were detected in both images
        if 'faces1' not in result or len(result['faces1']) == 0:
            return {
                'success': False,
                'error': "No face detected in the face photo",
                'match': False,
                'confidence': 0
            }
        
        if 'faces2' not in result or len(result['faces2']) == 0:
            return {
                'success': False,
                'error': "No face detected in the NID card",
                'match': False,
                'confidence': 0
            }
        
        # Handle multiple faces in face photo (should still be single)
        if len(result['faces1']) > 1:
            return {
                'success': False,
                'error': "Multiple faces detected in face photo. Please use image with single face.",
                'match': False,
                'confidence': 0
            }
        
        # Handle multiple faces in NID card (select the largest one)
        selected_nid_face = None
        multiple_faces_info = {}
        
        if len(result['faces2']) > 1:
            logger.info(f"Multiple faces detected in NID card ({len(result['faces2'])} faces). Selecting the largest face...")
            selected_nid_face = self.get_largest_face(result['faces2'])
            
            if selected_nid_face:
                # Get face rectangle info for logging
                face_rect = selected_nid_face.get('face_rectangle', {})
                logger.info(f"Selected main face with dimensions: {face_rect.get('width', 'unknown')}x{face_rect.get('height', 'unknown')} pixels")
                multiple_faces_info = {
                    'selected_face_dimensions': f"{face_rect.get('width', 'unknown')}x{face_rect.get('height', 'unknown')}"
                }
            else:
                return {
                    'success': False,
                    'error': "Could not select appropriate face from NID card",
                    'match': False,
                    'confidence': 0
                }
        else:
            selected_nid_face = result['faces2'][0]
        
        # Get confidence score
        confidence = result.get('confidence', 0)
        
        # Determine if it's a match based on threshold
        is_match = confidence >= confidence_threshold
        
        # Prepare additional info
        additional_info = {
            'faces_in_face_photo': len(result['faces1']),
            'faces_in_nid_card': len(result['faces2']),
            'used_largest_nid_face': len(result['faces2']) > 1,
            **multiple_faces_info
        }
        
        return {
            'success': True,
            'match': is_match,
            'confidence': confidence,
            'threshold_used': confidence_threshold,
            'face1_quality': result['faces1'][0].get('face_quality', {}),
            'face2_quality': selected_nid_face.get('face_quality', {}),
            'additional_info': additional_info,
            'message': f"{'Match' if is_match else 'No match'} - Confidence: {confidence}%"
        }
    
    def validate_nid_document_with_ocr(self, image_data: bytes) -> dict:
        """
        Validate if the uploaded image is actually an NID card using Face++ OCR API.
        
        Args:
            image_data (bytes): Image data to validate
        
        Returns:
            dict: Validation result with OCR text and document indicators
        """
        try:
            files = {
                'image_file': ('nid.jpg', image_data, 'image/jpeg')
            }
            
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret
            }
            
            response = requests.post(self.ocr_url, files=files, data=data)
            
            if response.status_code != 200:
                return {
                    'is_valid_nid': False,
                    'error': f"OCR API request failed: {response.status_code}",
                    'confidence': 0
                }
            
            result = response.json()
            
            if 'error_message' in result:
                return {
                    'is_valid_nid': False,
                    'error': f"OCR API Error: {result['error_message']}",
                    'confidence': 0
                }
            
            # Extract text from OCR result
            extracted_text = ""
            if 'result' in result and 'text' in result['result']:
                for text_item in result['result']['text']:
                    extracted_text += text_item.get('value', '') + " "
            
            extracted_text = extracted_text.lower().strip()
            
            # Define NID/document indicators (common terms found in official documents)
            nid_indicators = [
                'national', 'identity', 'card', 'government', 'republic', 'bangladesh',
                'citizen', 'birth', 'date', 'father', 'mother', 'address', 'signature',
                'id', 'no', 'serial', 'issue', 'expire', 'valid', 'official', 'ministry',
                'department', 'registration', 'voter', 'passport', 'license', 'authority'
            ]
            
            # Count how many indicators are found
            indicators_found = 0
            found_indicators = []
            
            for indicator in nid_indicators:
                if indicator in extracted_text:
                    indicators_found += 1
                    found_indicators.append(indicator)
            
            # Calculate confidence based on indicators found
            confidence = min((indicators_found / len(nid_indicators)) * 100, 100)
            
            # Consider it a valid NID if we find at least 2 indicators
            is_valid_nid = indicators_found >= 2
            
            return {
                'is_valid_nid': is_valid_nid,
                'confidence': confidence,
                'indicators_found': indicators_found,
                'found_indicators': found_indicators,
                'extracted_text': extracted_text[:200],  # First 200 chars for debugging
                'total_text_length': len(extracted_text)
            }
            
        except Exception as e:
            logger.error(f"Error in OCR validation: {str(e)}")
            return {
                'is_valid_nid': False,
                'error': f"OCR validation failed: {str(e)}",
                'confidence': 0
            }
    
    def validate_face_photo_characteristics(self, image_data: bytes) -> dict:
        """
        Validate if the uploaded image has characteristics of a regular photo (not a document).
        
        Args:
            image_data (bytes): Image data to validate
        
        Returns:
            dict: Validation result with photo characteristics
        """
        try:
            files = {
                'image_file': ('photo.jpg', image_data, 'image/jpeg')
            }
            
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'return_attributes': 'blur,eyestatus,emotion,beauty,headpose'
            }
            
            response = requests.post(self.detect_url, files=files, data=data)
            
            if response.status_code != 200:
                return {
                    'is_valid_photo': False,
                    'error': f"Face detection API failed: {response.status_code}",
                    'confidence': 0
                }
            
            result = response.json()
            
            if 'error_message' in result:
                return {
                    'is_valid_photo': False,
                    'error': f"Face detection error: {result['error_message']}",
                    'confidence': 0
                }
            
            if 'faces' not in result or len(result['faces']) == 0:
                return {
                    'is_valid_photo': False,
                    'error': "No face detected in photo",
                    'confidence': 0
                }
            
            # Analyze the first (and should be only) face
            face = result['faces'][0]
            face_rect = face.get('face_rectangle', {})
            attributes = face.get('attributes', {})
            
            # Calculate face-to-image ratio (photos typically have larger face ratios)
            image_width = result.get('image_width', 1)
            image_height = result.get('image_height', 1)
            face_width = face_rect.get('width', 0)
            face_height = face_rect.get('height', 0)
            
            face_area = face_width * face_height
            image_area = image_width * image_height
            face_ratio = (face_area / image_area) * 100 if image_area > 0 else 0
            
            # Photo characteristics scoring
            photo_score = 0
            characteristics = {}
            
            # 1. Face size ratio (photos typically have larger faces)
            if face_ratio > 5:  # Face takes up more than 5% of image
                photo_score += 25
                characteristics['good_face_ratio'] = True
            else:
                characteristics['good_face_ratio'] = False
            
            # 2. Blur analysis (photos can have some blur, documents are usually sharp)
            blur_info = attributes.get('blur', {})
            blur_level = blur_info.get('blurness', {}).get('value', 0)
            if 0 < blur_level < 50:  # Some natural blur is okay for photos
                photo_score += 20
                characteristics['natural_blur'] = True
            else:
                characteristics['natural_blur'] = False
            
            # 3. Head pose (photos often have slight angles)
            headpose = attributes.get('headpose', {})
            yaw = abs(headpose.get('yaw_angle', 0))
            pitch = abs(headpose.get('pitch_angle', 0))
            roll = abs(headpose.get('roll_angle', 0))
            
            if yaw < 30 and pitch < 30 and roll < 30:  # Natural pose variations
                photo_score += 25
                characteristics['natural_pose'] = True
            else:
                characteristics['natural_pose'] = False
            
            # 4. Multiple faces check (documents might have multiple photos)
            if len(result['faces']) == 1:
                photo_score += 30
                characteristics['single_face'] = True
            else:
                characteristics['single_face'] = False
            
            is_valid_photo = photo_score >= 50  # At least 50% confidence
            
            return {
                'is_valid_photo': is_valid_photo,
                'confidence': photo_score,
                'face_ratio': face_ratio,
                'characteristics': characteristics,
                'faces_detected': len(result['faces']),
                'blur_level': blur_level
            }
            
        except Exception as e:
            logger.error(f"Error in photo validation: {str(e)}")
            return {
                'is_valid_photo': False,
                'error': f"Photo validation failed: {str(e)}",
                'confidence': 0
            }
    
    def extract_nid_information(self, image_data: bytes) -> Dict[str, Any]:
        """
        Extract NID information (Name and ID No./NID No.) from NID card image using OpenAI Vision API.
        
        Args:
            image_data (bytes): NID card image data
            
        Returns:
            dict: Extracted information with name, id_number, and confidence
        """
        try:
            if not self.openai_api_key:
                return {
                    'success': False,
                    'error': 'OpenAI API key not configured',
                    'name': None,
                    'id_number': None,
                    'confidence': 0
                }
            
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare the prompt for OpenAI Vision
            prompt = """
            Analyze this NID card image and extract the following information:
            1. Name (the person's full name)
            2. ID Number (look for "ID No." or "NID No." - it might be labeled differently)
            
            Return the information in this exact JSON format:
            {
                "name": "Full Name Here",
                "id_number": "ID123456789",
                "confidence": 0.95
            }
            
            If you cannot find the information clearly, set the value to null.
            The confidence should be between 0 and 1, where 1 means very confident.
            """
            
            # Prepare the API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": "gpt-4o-mini",  # Using vision-capable model
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 300,
                "temperature": 0.1  # Low temperature for consistent extraction
            }
            
            # Make the API call
            response = requests.post(self.openai_vision_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'OpenAI API error: {response.status_code}',
                    'name': None,
                    'id_number': None,
                    'confidence': 0
                }
            
            result = response.json()
            
            # Extract the response content
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                logger.info(f"OpenAI Vision response: {content}")
                
                try:
                    # Clean up markdown if present
                    cleaned_content = content.strip()
                    if cleaned_content.startswith('```json'):
                        cleaned_content = cleaned_content[7:]
                    elif cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]
                    cleaned_content = cleaned_content.strip()
                    
                    # Try to parse as JSON
                    extracted_data = json.loads(cleaned_content)
                    
                    return {
                        'success': True,
                        'name': extracted_data.get('name'),
                        'id_number': extracted_data.get('id_number'),
                        'confidence': extracted_data.get('confidence', 0),
                        'raw_response': content
                    }
                    
                except json.JSONDecodeError:
                    # If not valid JSON, try to extract manually
                    logger.warning("OpenAI response not in JSON format, attempting manual extraction")
                    
                    name = None
                    id_number = None
                    
                    # Simple text extraction (fallback)
                    content_lower = content.lower()
                    if 'name' in content_lower and ':' in content:
                        # Try to extract name
                        lines = content.split('\n')
                        for line in lines:
                            if 'name' in line.lower() and ':' in line:
                                name = line.split(':', 1)[1].strip().strip('"')
                                break
                    
                    if 'id' in content_lower and ':' in content:
                        # Try to extract ID number
                        lines = content.split('\n')
                        for line in lines:
                            if ('id' in line.lower() or 'nid' in line.lower()) and ':' in line:
                                id_number = line.split(':', 1)[1].strip().strip('"')
                                break
                    
                    return {
                        'success': True,
                        'name': name,
                        'id_number': id_number,
                        'confidence': 0.5,  # Lower confidence for manual extraction
                        'raw_response': content
                    }
            
            return {
                'success': False,
                'error': 'No valid response from OpenAI Vision API',
                'name': None,
                'id_number': None,
                'confidence': 0
            }
            
        except Exception as e:
            logger.error(f"Error extracting NID information: {str(e)}")
            return {
                'success': False,
                'error': f'Error extracting NID information: {str(e)}',
                'name': None,
                'id_number': None,
                'confidence': 0
            }
    
    def process_uploaded_image(self, image_data: bytes) -> Optional[bytes]:
        """Process uploaded image and return optimized data."""
        try:
            # Process the image
            processed_data = self.resize_image_if_needed(image_data)
            return processed_data
        except Exception as e:
            logger.error(f"Error processing uploaded image: {str(e)}")
            return None