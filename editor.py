# editor.py
"""
PDF 문서를 직접 수정하여 워터마크를 제거하는 함수들을 포함하는 모듈입니다.
fitz.Document 객체와 제거할 객체의 xref 리스트를 입력받아 작업을 수행합니다.
"""

import fitz  # PyMuPDF
import re
from typing import List, Dict, Set

# -----------------------------------------------------------------------------
# --- PDF 편집 헬퍼 함수 ---
# -----------------------------------------------------------------------------

def map_xrefs_to_names(doc: fitz.Document, xrefs: List[int]) -> Dict[int, str]:
    """
    이미지 xref 리스트를 페이지 리소스에서 사용하는 이름(예: /Im1)에 매핑합니다.
    Content Stream에서 이미지 호출 명령을 찾기 위해 필요합니다.

    Args:
        doc (fitz.Document): 작업 대상 PyMuPDF 문서 객체.
        xrefs (List[int]): 이름을 찾을 이미지 객체의 xref 리스트.

    Returns:
        Dict[int, str]: {xref: "이미지이름"} 형태의 딕셔너리.
    """
    name_map = {}
    xrefs_to_find = set(xrefs)

    for page in doc:
        # 모든 xref의 이름을 찾았으면 더 이상 순회할 필요가 없음
        if not xrefs_to_find:
            break
            
        try:
            # 페이지의 /Resources 객체에서 XObject 딕셔너리를 직접 파싱
            # xref_object는 압축 해제된 원시 문자열을 반환
            resources = doc.xref_object(page.xref)
            for xref in list(xrefs_to_find):
                # /Im... <xref> 0 R 패턴 검색
                match = re.search(rf"/(Im\d+)\s+{xref}\s+0\s+R", resources)
                if match:
                    name = match.group(1)
                    name_map[xref] = name
                    xrefs_to_find.remove(xref)
        except Exception as e:
            # 리소스가 없는 페이지 등 예외 발생 시 다음 페이지로 넘어감
            print(f"페이지 {page.number} 리소스 파싱 중 오류: {e}")
            continue
            
    if xrefs_to_find:
        print(f"경고: 다음 xref의 이름을 찾지 못했습니다: {xrefs_to_find}")

    print(f"이미지 이름 매핑 완료: {name_map}")
    return name_map

def clean_content_streams(doc: fitz.Document, image_names: List[str]):
    """
    모든 페이지의 Content Stream을 순회하며 지정된 이미지 이름들을
    호출하는 그리기(Do) 명령 블록을 제거합니다.

    Args:
        doc (fitz.Document): 작업 대상 PyMuPDF 문서 객체.
        image_names (List[str]): 제거할 이미지의 이름 리스트 (예: ["Im1", "Im2"]).
    """
    if not image_names:
        return

    # 여러 이미지 이름을 |로 연결하는 정규표현식 패턴 생성 (예: /Im1|/Im2)
    names_pattern = "|".join(re.escape(name) for name in image_names)
    
    # 워터마크를 그리는 일반적인 블록 패턴: q ... /Im... Do ... Q
    # q/Q는 그래픽 상태를 저장/복원하는 명령으로, 보통 하나의 객체를 그릴 때 감싸줍니다.
    # re.DOTALL 플래그는 '.'이 개행 문자도 포함하도록 합니다.
    watermark_pattern = re.compile(
        rf"q\s*.*?/({names_pattern})\s+Do\s*.*?Q",
        flags=re.DOTALL
    )

    print(f"Content Stream에서 다음 이미지 호출 제거 시도: {image_names}")
    for page in doc:
        try:
            for content_xref in page.get_contents():
                # 스트림을 디코딩할 때, 예상치 못한 인코딩에 대비해 'latin-1' 사용
                stream = doc.xref_stream(content_xref).decode("latin-1")
                
                # 정규표현식을 사용해 워터마크 블록을 빈 문자열로 치환
                cleaned_stream = watermark_pattern.sub("", stream)

                if cleaned_stream != stream:
                    print(f"페이지 {page.number} (xref={content_xref})의 Content Stream 정리 완료.")
                    doc.update_stream(content_xref, cleaned_stream.encode("latin-1"))
        except Exception as e:
            print(f"페이지 {page.number} 콘텐츠 정리 중 오류: {e}")

def delete_objects_and_smasks(doc: fitz.Document, xrefs: List[int]) -> int:
    """
    주어진 xref 리스트에 해당하는 객체와, 그 객체와 연관된
    SMask(투명도 마스크) 객체를 PDF에서 완전히 삭제합니다.

    Args:
        doc (fitz.Document): 작업 대상 PyMuPDF 문서 객체.
        xrefs (List[int]): 삭제할 이미지 객체의 xref 리스트.

    Returns:
        int: 실제로 삭제된 총 객체 수.
    """
    deleted_xrefs: Set[int] = set()
    for xref in xrefs:
        # 1. SMask 객체 찾기 및 삭제
        try:
            obj_definition = doc.xref_object(xref)
            # /SMask <smask_xref> 0 R 패턴 검색
            smask_match = re.search(r"/SMask\s+(\d+)\s+0\s+R", obj_definition)
            if smask_match:
                smask_xref = int(smask_match.group(1))
                if smask_xref not in deleted_xrefs:
                    doc._delete_object(smask_xref)
                    deleted_xrefs.add(smask_xref)
                    print(f"SMask 객체 (xref={smask_xref}) 삭제 완료.")
        except Exception as e:
            # 객체 정의를 읽지 못하는 등 예외 발생 시 무시하고 진행
            print(f"SMask 탐색 중 오류 (xref={xref}): {e}")
            pass

        # 2. 원본 이미지 객체 삭제
        try:
            if xref not in deleted_xrefs:
                doc._delete_object(xref)
                deleted_xrefs.add(xref)
                print(f"이미지 객체 (xref={xref}) 삭제 완료.")
        except Exception as e:
            print(f"이미지 객체 삭제 실패 (xref={xref}): {e}")
    
    return len(deleted_xrefs)

# -----------------------------------------------------------------------------
# --- 메인 편집 함수 (프로세스 통합) ---
# -----------------------------------------------------------------------------

def remove_watermarks_by_xrefs(doc: fitz.Document, image_xrefs: List[int]):
    """
    워터마크 제거 프로세스 전체를 실행하는 메인 함수입니다.
    이 함수는 GUI의 백그라운드 워커에서 직접 호출될 수 있습니다.
    
    Args:
        doc (fitz.Document): 수정할 PyMuPDF 문서 객체.
        image_xrefs (List[int]): 사용자가 선택한, 제거할 워터마크 이미지의 xref 리스트.
    """
    if not image_xrefs:
        print("제거할 워터마크 xref가 없습니다.")
        return

    print("-" * 20)
    print(f"총 {len(image_xrefs)}개의 선택된 워터마크 객체 제거 시작.")
    
    # 1. XRef를 이미지 이름으로 변환
    name_map = map_xrefs_to_names(doc, image_xrefs)
    
    # 2. Content Stream에서 이미지 호출 명령어 제거
    clean_content_streams(doc, list(name_map.values()))
    
    # 3. 이미지 및 관련 객체(SMask) 완전 삭제
    delete_objects_and_smasks(doc, image_xrefs)
    
    print("워터마크 제거 작업 완료.")
    print("-" * 20)

