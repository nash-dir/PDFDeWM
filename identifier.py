# identifier.py
"""
PDF 문서 내에서 워터마크로 의심되는 객체를 식별하는 함수들을 포함하는 모듈입니다.
각 함수는 fitz.Document 객체를 입력받아 워터마크 후보의 xref 리스트를 반환합니다.
"""

import fitz  # PyMuPDF
from collections import defaultdict
from typing import List, Dict, Any

# -----------------------------------------------------------------------------
# --- 기본 워터마크 식별 전략: 공통성 기반 탐지 ---
# -----------------------------------------------------------------------------

def find_by_commonality(doc: fitz.Document, min_page_ratio: float = 0.8) -> List[int]:
    """
    문서의 여러 페이지에 걸쳐 공통적으로 나타나는 이미지를 워터마크로 식별합니다.
    가장 안정적이고 일반적인 워터마크 탐지 방법입니다.

    Args:
        doc (fitz.Document): 분석할 PyMuPDF 문서 객체.
        min_page_ratio (float): 이미지가 워터마크로 간주되기 위해
                                나타나야 하는 최소 페이지 비율. (기본값: 0.8)

    Returns:
        List[int]: 워터마크로 의심되는 이미지 객체의 xref 리스트.
    """
    if not isinstance(doc, fitz.Document):
        raise TypeError("doc 인자는 fitz.Document 객체여야 합니다.")
    
    total_pages = len(doc)
    if total_pages == 0:
        return []

    image_counts = defaultdict(int)

    # 1. 각 페이지를 순회하며 이미지 xref의 등장 횟수를 계산합니다.
    for page in doc:
        # 한 페이지에 동일 이미지가 여러 번 사용되어도 한 번만 카운트하기 위해 set 사용
        xrefs_on_page = {img[0] for img in page.get_images(full=True)}
        for xref in xrefs_on_page:
            image_counts[xref] += 1
            
    # 2. 최소 등장 페이지 수를 계산합니다.
    #    (예: 10페이지 문서에 0.8 비율이면 8페이지 이상 등장해야 함)
    min_pages = max(1, int(total_pages * min_page_ratio))

    # 3. 최소 페이지 수 이상 등장한 이미지 xref만 필터링하여 반환합니다.
    common_xrefs = [xref for xref, count in image_counts.items() if count >= min_pages]
    
    print(f"총 {total_pages} 페이지 중 {min_pages} 페이지 이상 등장한 이미지 탐색...")
    print(f"발견된 공통 이미지 xref: {common_xrefs}")
    
    return common_xrefs


# -----------------------------------------------------------------------------
# --- 확장/대안 식별 전략 (향후 구현을 위한 예시) ---
# -----------------------------------------------------------------------------

def find_by_transparency(doc: fitz.Document) -> List[int]:
    """
    (향후 구현) 투명도(alpha) 값을 가진 이미지를 워터마크 후보로 식별합니다.
    워터마크는 종종 반투명하게 처리되기 때문에 유효한 전략이 될 수 있습니다.
    """
    print("참고: 투명도 기반 식별 기능은 아직 구현되지 않았습니다.")
    # 예시 로직:
    # 1. 모든 ExtGState 객체를 순회
    # 2. /ca 또는 /CA 값이 1.0 미만인 ExtGState를 찾음
    # 3. 해당 ExtGState를 사용하는 이미지 객체의 xref를 수집
    return []

def find_text_watermarks(doc: fitz.Document, min_page_ratio: float = 0.8) -> List[Dict[str, Any]]:
    """
    (향후 구현) 여러 페이지에 걸쳐 동일한 위치에 반복적으로 나타나는 텍스트를
    워터마크로 식별합니다.
    """
    print("참고: 텍스트 기반 워터마크 식별 기능은 아직 구현되지 않았습니다.")
    # 예시 로직:
    # 1. 모든 페이지에서 텍스트 블록과 위치(bbox) 정보를 추출
    # 2. 내용과 위치가 거의 동일한 텍스트 블록이 몇 페이지에 걸쳐 나타나는지 카운트
    # 3. min_page_ratio를 충족하는 텍스트 블록 정보를 반환
    return []


# -----------------------------------------------------------------------------
# --- 메인 식별 함수 (전략 선택) ---
# -----------------------------------------------------------------------------

def find_watermark_candidates(
    doc: fitz.Document,
    strategy: str = 'commonality',
    **kwargs
) -> List[int]:
    """
    지정된 전략을 사용하여 워터마크 후보를 식별하는 메인 함수입니다.

    Args:
        doc (fitz.Document): 분석할 PyMuPDF 문서 객체.
        strategy (str): 사용할 식별 전략.
                        'commonality' (기본값), 'transparency' 등.
        **kwargs: 각 전략에 필요한 추가 인자들.
                  (예: commonality 전략의 min_page_ratio)

    Returns:
        List[int]: 식별된 워터마크 후보의 xref 리스트.
    
    Raises:
        ValueError: 지원되지 않는 전략 이름이 주어질 경우 발생.
    """
    if strategy == 'commonality':
        min_page_ratio = kwargs.get('min_page_ratio', 0.8)
        return find_by_commonality(doc, min_page_ratio)
    
    elif strategy == 'transparency':
        return find_by_transparency(doc)
    
    # 나중에 다른 전략을 추가할 수 있습니다.
    # elif strategy == 'text':
    #     return find_text_watermarks(doc, **kwargs)
    
    else:
        raise ValueError(f"알 수 없는 식별 전략입니다: {strategy}")

