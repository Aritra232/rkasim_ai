# from fastapi import APIRouter, File, UploadFile, HTTPException
# from fastapi.responses import FileResponse
# import os
# import uuid
# import cv2

# from com.mhire.app.services.nid_verification.nid_verification import NIDDetector, process_uploaded_file, encode_image_to_base64
# from com.mhire.app.services.nid_verification.nid_verification_schema import DetectionResult, DetectionResultWithImage

# # Initialize router
# router = APIRouter(
#     prefix="/api/v1",
#     tags=["NID Verification"]
# )
# # Initialize the detector
# detector = NIDDetector()

# # Create temp directory for storing processed images
# TEMP_DIR = "temp_images"
# os.makedirs(TEMP_DIR, exist_ok=True)


# # @router.get("/")
# # async def nid_verification_info():
# #     """NID verification service information."""
# #     return {
# #         "message": "NID Card Detection Service",
# #         "version": "1.0.0",
# #         "endpoints": {
# #             "POST /detect": "Upload image and detect NID card",
# #             "POST /detect-with-visualization": "Upload image and get detection with visualization",
# #             "POST /detect-and-save": "Upload image, detect NID card and save result",
# #             "GET /download/{filename}": "Download processed result image"
# #         }
# #     }


# @router.post("/detect", response_model=DetectionResult)
# async def detect_nid(file: UploadFile = File(...)):
#     """
#     Detect NID card in uploaded image.
    
#     Args:
#         file: Image file (supports PNG, JPG, JPEG, BMP, etc.)
    
#     Returns:
#         Detection results with confidence score and details
#     """
#     # Validate file type
#     if not file.content_type.startswith('image/'):
#         raise HTTPException(status_code=400, detail="File must be an image")
    
#     try:
#         # Read file content
#         file_content = await file.read()
        
#         # Process image
#         image = process_uploaded_file(file_content)
        
#         # Detect NID
#         is_nid, detection_info = detector.is_nid_card(image)
        
#         # Prepare response
#         message = "NID card detected" if is_nid else "No NID card detected"
#         if detection_info['confidence_score'] > 0 and not is_nid:
#             message += f" (partial match with {detection_info['confidence_score']:.2f} confidence)"
        
#         return DetectionResult(
#             is_nid_card=is_nid,
#             confidence_score=detection_info['confidence_score'],
#             rectangular_contours_found=detection_info['rectangular_contours_found'],
#             valid_aspect_ratios=detection_info['valid_aspect_ratios'],
#             faces_detected=detection_info['faces_detected'],
#             message=message
#         )
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


# # @router.post("/detect-with-visualization", response_model=DetectionResultWithImage)
# # async def detect_nid_with_visualization(file: UploadFile = File(...)):
# #     """
# #     Detect NID card in uploaded image and return result with visualization.
    
# #     Args:
# #         file: Image file (supports PNG, JPG, JPEG, BMP, etc.)
    
# #     Returns:
# #         Detection results with confidence score, details, and base64-encoded result image
# #     """
# #     # Validate file type
# #     if not file.content_type.startswith('image/'):
# #         raise HTTPException(status_code=400, detail="File must be an image")
    
# #     try:
# #         # Read file content
# #         file_content = await file.read()
        
# #         # Process image
# #         image = process_uploaded_file(file_content)
        
# #         # Detect NID
# #         is_nid, detection_info = detector.is_nid_card(image)
        
# #         # Create visualization
# #         result_image = detector.visualize_detection(image, detection_info)
        
# #         # Encode result image to base64
# #         result_image_base64 = encode_image_to_base64(result_image)
        
# #         # Prepare response
# #         message = "NID card detected" if is_nid else "No NID card detected"
# #         if detection_info['confidence_score'] > 0 and not is_nid:
# #             message += f" (partial match with {detection_info['confidence_score']:.2f} confidence)"
        
# #         return DetectionResultWithImage(
# #             is_nid_card=is_nid,
# #             confidence_score=detection_info['confidence_score'],
# #             rectangular_contours_found=detection_info['rectangular_contours_found'],
# #             valid_aspect_ratios=detection_info['valid_aspect_ratios'],
# #             faces_detected=detection_info['faces_detected'],
# #             message=message,
# #             result_image_base64=result_image_base64
# #         )
        
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


# # @router.post("/detect-and-save")
# # async def detect_nid_and_save_result(file: UploadFile = File(...)):
# #     """
# #     Detect NID card and save the result image to temp directory.
    
# #     Args:
# #         file: Image file (supports PNG, JPG, JPEG, BMP, etc.)
    
# #     Returns:
# #         Detection results and path to saved result image
# #     """
# #     # Validate file type
# #     if not file.content_type.startswith('image/'):
# #         raise HTTPException(status_code=400, detail="File must be an image")
    
# #     try:
# #         # Read file content
# #         file_content = await file.read()
        
# #         # Process image
# #         image = process_uploaded_file(file_content)
        
# #         # Detect NID
# #         is_nid, detection_info = detector.is_nid_card(image)
        
# #         # Create visualization
# #         result_image = detector.visualize_detection(image, detection_info)
        
# #         # Save result image
# #         result_filename = f"result_{uuid.uuid4().hex[:8]}.jpg"
# #         result_path = os.path.join(TEMP_DIR, result_filename)
# #         cv2.imwrite(result_path, result_image)
        
# #         # Prepare response
# #         message = "NID card detected" if is_nid else "No NID card detected"
# #         if detection_info['confidence_score'] > 0 and not is_nid:
# #             message += f" (partial match with {detection_info['confidence_score']:.2f} confidence)"
        
# #         return {
# #             "is_nid_card": is_nid,
# #             "confidence_score": detection_info['confidence_score'],
# #             "rectangular_contours_found": detection_info['rectangular_contours_found'],
# #             "valid_aspect_ratios": detection_info['valid_aspect_ratios'],
# #             "faces_detected": detection_info['faces_detected'],
# #             "message": message,
# #             "result_image_path": result_path,
# #             "download_url": f"/nid-verification/download/{result_filename}"
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


# # @router.get("/download/{filename}")
# # async def download_result_image(filename: str):
# #     """
# #     Download a processed result image.
    
# #     Args:
# #         filename: Name of the result image file
    
# #     Returns:
# #         File response with the image
# #     """
# #     file_path = os.path.join(TEMP_DIR, filename)
    
# #     if not os.path.exists(file_path):
# #         raise HTTPException(status_code=404, detail="File not found")
    
# #     return FileResponse(
# #         path=file_path,
# #         media_type='image/jpeg',
# #         filename=filename
# #     )