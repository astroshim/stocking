def get_filters(args, optional_params=None):
    filters = parse_request_args(
        args,
        optional_params=optional_params,
    )

    # 기본값 설정
    filters.setdefault('page', 0)
    filters.setdefault('per_page', 10)
    return filters


def parse_request_args(args, required_params=None, optional_params=None, type_conversions=None):
    """
    요청 파라미터를 파싱하여 딕셔너리로 반환하는 유틸리티 함수

    Args:
        required_params (list): 필수 파라미터 목록
        optional_params (list): 선택적 파라미터 목록
        type_conversions (dict): 파라미터별 타입 변환 함수 매핑

    Returns:
        dict: 파싱된 파라미터 딕셔너리
    """
    filters = {}

    # 필수 파라미터 처리
    if required_params:
        for param in required_params:
            if param in args:
                filters[param] = args.get(param)
            else:
                # 기본값이나 에러 처리 로직 추가 가능
                pass

    # 선택적 파라미터 처리
    if optional_params:
        for param in optional_params:
            if param in args and args.get(param) is not None:
                filters[param] = args.get(param)

    # 타입 변환 처리
    if type_conversions:
        for param, converter in type_conversions.items():
            if param in filters:
                try:
                    filters[param] = converter(filters[param])
                except (ValueError, TypeError):
                    # 변환 실패 처리 로직 추가 가능
                    pass

    return filters
