import logging
from fastapi import APIRouter, Depends, Query, status

from app.api.v1.schemas.storage_schema import PresignedUrlResponse
from app.services.s3_service import S3Service
from app.utils.response_helper import create_response
from app.config.get_current_user import get_current_user

router = APIRouter()


@router.get("/upload_url", summary="파일 upload를 위한 Presigned URL 생성",
            description="""
            upload_url 주소에 PUT 으로 파일을 binary로 업로드합니다. 
            
            요청 예) 
            curl -X PUT -T file.jpg "upload_url" 

stocking.s3.amazonaws.com
curl -X PUT -T /Users/hyungsungshim/Downloads/0047.jpg "https://stocking.s3.amazonaws.com/media/test/fe9f9f11-54a7-47a1-b10a-1f2079349a02.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA3JCOK45XFXF2VVGA%2F20250722%2Fap-northeast-2%2Fs3%2Faws4_request&X-Amz-Date=20250722T081342Z&X-Amz-Expires=300&X-Amz-SignedHeaders=host&X-Amz-Signature=29aaecef049529dbfaf253954954d00f3226cb599f2196ed7d9d3d4c5439570a"
            """)
def generate_presigned_url(
        extension: str = Query(..., description="파일 확장자 (. 제외)"),
        # user_id: str = Depends(get_current_user),
        # s3_service: S3Service = Depends(get_s3_service)
):
    user_id = "routine-marketing"

    try:
        if not extension:
            return create_response(
                {"error": "param is not valid."},
                status.HTTP_400_BAD_REQUEST,
                "failed"
            )

        presigned_url = S3Service().generate_presigned_url(f"media/{user_id}", extension)
        logging.info(f"presigned_url: {presigned_url}")

        return create_response(
            PresignedUrlResponse(**presigned_url).model_dump(),
            status.HTTP_200_OK,
            "success"
        )
    except Exception as err:
        return create_response(
            {"error": str(err)},
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "failed"
        )
