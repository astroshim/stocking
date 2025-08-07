from pydantic import BaseModel

class PresignedUrlResponse(BaseModel):
    """프리사인드 URL 응답 스키마"""
    upload_url: str
    download_url: str
