from fastapi import Request

def get_client_ip(request: Request):
    """
    FastAPI에서 클라이언트의 실제 IP 주소를 가져오는 함수

    Args:
        request (Request): FastAPI의 Request 객체

    Returns:
        str: 클라이언트의 IP 주소
    """
    # 프록시/로드밸런서 환경에서 가장 많이 사용되는 헤더들 확인
    headers_to_check = [
        'X-Forwarded-For',
        'X-Real-IP',
        'CF-Connecting-IP',  # Cloudflare
        'True-Client-IP'
    ]

    for header in headers_to_check:
        if header.lower() in request.headers:
            ip = request.headers[header.lower()]
            # 여러 IP가 있는 경우 첫 번째 IP 반환
            if ',' in ip:
                return ip.split(',')[0].strip()
            return ip

    # 헤더에 없으면 기본 IP 반환
    return request.client.host
