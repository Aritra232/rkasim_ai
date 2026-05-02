# import cv2
# import numpy as np
# import os
# from typing import Tuple, List
# import base64


# class NIDDetector:
#     def __init__(self):
#         """Initialize the NID detector with default parameters."""
#         # Aspect ratio range for NID cards (typical ID card ratio is ~1.6)
#         self.min_aspect_ratio = 1.4
#         self.max_aspect_ratio = 1.8
        
#         # Minimum and maximum area for valid NID cards (in pixels)
#         self.min_area = 10000  # Adjust based on your image resolution
#         self.max_area = 500000
        
#         # Face detection cascade
#         self.face_cascade = None
#         self.load_face_cascade()
        
#     def load_face_cascade(self):
#         """Load Haar cascade for face detection."""
#         try:
#             # Try to load the cascade file
#             cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
#             self.face_cascade = cv2.CascadeClassifier(cascade_path)
            
#             if self.face_cascade.empty():
#                 print("Warning: Could not load face cascade classifier")
#                 self.face_cascade = None
#         except Exception as e:
#             print(f"Error loading face cascade: {e}")
#             self.face_cascade = None
    
#     def preprocess_image(self, image: np.ndarray) -> np.ndarray:
#         """Preprocess the image for better contour detection."""
#         # Convert to grayscale
#         gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
#         # Apply Gaussian blur to reduce noise
#         blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
#         # Apply adaptive threshold
#         thresh = cv2.adaptiveThreshold(
#             blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
#             cv2.THRESH_BINARY, 11, 2
#         )
        
#         # Apply morphological operations to clean up
#         kernel = np.ones((3, 3), np.uint8)
#         cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
#         return cleaned, gray
    
#     def detect_rectangular_contours(self, processed_image: np.ndarray) -> List[np.ndarray]:
#         """Detect rectangular contours that could be NID cards."""
#         # Find contours
#         contours, _ = cv2.findContours(
#             processed_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
#         )
        
#         rectangular_contours = []
        
#         for contour in contours:
#             # Calculate area
#             area = cv2.contourArea(contour)
            
#             # Filter by area
#             if area < self.min_area or area > self.max_area:
#                 continue
            
#             # Approximate the contour
#             epsilon = 0.02 * cv2.arcLength(contour, True)
#             approx = cv2.approxPolyDP(contour, epsilon, True)
            
#             # Check if the contour has 4 corners (rectangular)
#             if len(approx) == 4:
#                 rectangular_contours.append(approx)
        
#         return rectangular_contours
    
#     def check_aspect_ratio(self, contour: np.ndarray) -> bool:
#         """Check if the contour has an aspect ratio typical of NID cards."""
#         # Get bounding rectangle
#         x, y, w, h = cv2.boundingRect(contour)
#         aspect_ratio = max(w, h) / min(w, h)
        
#         return self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio
    
#     def detect_face_in_region(self, image: np.ndarray, contour: np.ndarray) -> bool:
#         """Detect if there's a face within the given contour region."""
#         if self.face_cascade is None:
#             print("Face cascade not loaded, skipping face detection")
#             return True  # Assume positive if face detection unavailable
        
#         # Create mask for the contour region
#         mask = np.zeros(image.shape[:2], dtype=np.uint8)
#         cv2.fillPoly(mask, [contour], 255)
        
#         # Extract the region of interest
#         x, y, w, h = cv2.boundingRect(contour)
#         roi = image[y:y+h, x:x+w]
#         roi_mask = mask[y:y+h, x:x+w]
        
#         # Apply mask to ROI
#         masked_roi = cv2.bitwise_and(roi, roi, mask=roi_mask)
        
#         # Convert to grayscale if needed
#         if len(masked_roi.shape) == 3:
#             gray_roi = cv2.cvtColor(masked_roi, cv2.COLOR_BGR2GRAY)
#         else:
#             gray_roi = masked_roi
        
#         # Detect faces
#         faces = self.face_cascade.detectMultiScale(
#             gray_roi,
#             scaleFactor=1.1,
#             minNeighbors=5,
#             minSize=(20, 20),  # Minimum face size
#             maxSize=(int(w*0.6), int(h*0.8))  # Maximum face size relative to card
#         )
        
#         # Check if we found at least one face
#         return len(faces) > 0
    
#     def is_nid_card(self, image: np.ndarray) -> Tuple[bool, dict]:
#         """
#         Main function to detect if the image contains an NID card.
        
#         Returns:
#             Tuple[bool, dict]: (is_nid, detection_info)
#         """
#         detection_info = {
#             'rectangular_contours_found': 0,
#             'valid_aspect_ratios': 0,
#             'faces_detected': 0,
#             'confidence_score': 0.0,
#             'contours': []
#         }
        
#         # Preprocess image
#         processed_image, gray_image = self.preprocess_image(image)
        
#         # Detect rectangular contours
#         rectangular_contours = self.detect_rectangular_contours(processed_image)
#         detection_info['rectangular_contours_found'] = len(rectangular_contours)
        
#         if len(rectangular_contours) == 0:
#             return False, detection_info
        
#         # Check each contour
#         valid_contours = []
        
#         for contour in rectangular_contours:
#             contour_info = {
#                 'contour': contour,
#                 'valid_aspect_ratio': False,
#                 'face_detected': False
#             }
            
#             # Check aspect ratio
#             if self.check_aspect_ratio(contour):
#                 contour_info['valid_aspect_ratio'] = True
#                 detection_info['valid_aspect_ratios'] += 1
                
#                 # Check for face
#                 if self.detect_face_in_region(image, contour):
#                     contour_info['face_detected'] = True
#                     detection_info['faces_detected'] += 1
#                     valid_contours.append(contour_info)
            
#             detection_info['contours'].append(contour_info)
        
#         # Calculate confidence score
#         if len(rectangular_contours) > 0:
#             aspect_ratio_score = detection_info['valid_aspect_ratios'] / len(rectangular_contours)
#             face_score = detection_info['faces_detected'] / max(detection_info['valid_aspect_ratios'], 1)
#             detection_info['confidence_score'] = (aspect_ratio_score + face_score) / 2
        
#         # Determine if it's an NID card
#         is_nid = len(valid_contours) > 0
        
#         return is_nid, detection_info
    
#     def visualize_detection(self, image: np.ndarray, detection_info: dict) -> np.ndarray:
#         """Visualize the detection results on the image."""
#         result_image = image.copy()
        
#         for i, contour_info in enumerate(detection_info['contours']):
#             contour = contour_info['contour']
            
#             # Choose color based on detection results
#             if contour_info['valid_aspect_ratio'] and contour_info['face_detected']:
#                 color = (0, 255, 0)  # Green for positive detection
#                 thickness = 3
#             elif contour_info['valid_aspect_ratio']:
#                 color = (0, 255, 255)  # Yellow for partial detection
#                 thickness = 2
#             else:
#                 color = (0, 0, 255)  # Red for invalid
#                 thickness = 1
            
#             # Draw contour
#             cv2.drawContours(result_image, [contour], -1, color, thickness)
            
#             # Add label
#             x, y, w, h = cv2.boundingRect(contour)
#             label = f"Contour {i+1}"
#             if contour_info['valid_aspect_ratio'] and contour_info['face_detected']:
#                 label += " (NID)"
#             cv2.putText(result_image, label, (x, y-10), 
#                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
#         return result_image


# def process_uploaded_file(file_content: bytes) -> np.ndarray:
#     """Convert uploaded file content to OpenCV image."""
#     try:
#         # Convert bytes to numpy array
#         nparr = np.frombuffer(file_content, np.uint8)
#         # Decode image
#         image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
#         if image is None:
#             raise ValueError("Could not decode image")
        
#         return image
#     except Exception as e:
#         from fastapi import HTTPException
#         raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")


# def encode_image_to_base64(image: np.ndarray) -> str:
#     """Encode OpenCV image to base64 string."""
#     try:
#         _, buffer = cv2.imencode('.jpg', image)
#         image_base64 = base64.b64encode(buffer).decode('utf-8')
#         return image_base64
#     except Exception as e:
#         from fastapi import HTTPException
#         raise HTTPException(status_code=500, detail=f"Error encoding image: {str(e)}")