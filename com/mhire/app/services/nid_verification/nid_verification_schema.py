# from pydantic import BaseModel
# from typing import Optional


# class DetectionResult(BaseModel):
#     is_nid_card: bool
#     confidence_score: float
#     rectangular_contours_found: int
#     valid_aspect_ratios: int
#     faces_detected: int
#     message: str


# class DetectionResultWithImage(DetectionResult):
#     result_image_base64: Optional[str] = None