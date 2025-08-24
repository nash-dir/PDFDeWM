# core.py
"""
GUI와 백엔드 로직(identifier, editor)을 연결하는 핵심 모듈입니다.
PDF 처리의 전체적인 흐름을 제어하는 함수들을 포함합니다.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any

# 애플리케이션의 다른 모듈 임포트
import identifier
import editor

# -----------------------------------------------------------------------------
# --- 핵심 프로세스 함수 ---
# -----------------------------------------------------------------------------

def scan_files_for_watermarks(
    file_paths: List[str], 
    min_page_ratio: float = 0.5
) -> Dict[int, Dict[str, Any]]:
    """
    여러 PDF 파일을 스캔하여 공통된 워터마크 후보를 찾습니다.
    GUI에서 썸네일을 표시하는 데 필요한 정보를 반환합니다.

    Args:
        file_paths (List[str]): 스캔할 PDF 파일 경로의 리스트.
        min_page_ratio (float): 워터마크로 판단할 최소 페이지 비율.

    Returns:
        Dict[int, Dict[str, Any]]: 
        {
            xref: {
                'pil_img': Pillow Image Object, 
                'doc_path': 원본 문서 경로, 
                'xref': xref 번호
            }
        } 형태의 딕셔너리.
    """
    all_candidates = {}
    
    for file_path in file_paths:
        try:
            doc = fitz.open(file_path)
            
            # identifier 모듈을 사용해 워터마크 후보 xref 찾기
            common_xrefs = identifier.find_by_commonality(doc, min_page_ratio)
            
            for xref in common_xrefs:
                # 이전에 발견되지 않은 후보인 경우에만 이미지 데이터 추출
                if xref not in all_candidates:
                    pix = fitz.Pixmap(doc, xref)
                    # Pillow Image 객체로 변환 (GUI에서 사용하기 위함)
                    # Pillow 라이브러리가 필요
                    from PIL import Image
                    mode = "RGBA" if pix.alpha else "RGB"
                    pil_img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
                    
                    all_candidates[xref] = {
                        'pil_img': pil_img,
                        'doc_path': file_path,
                        'xref': xref
                    }
            doc.close()
        except Exception as e:
            print(f"파일 스캔 중 오류 발생 ({Path(file_path).name}): {e}")
            continue
            
    return all_candidates


def process_and_remove_watermarks(
    file_paths: List[str], 
    output_dir: str, 
    xrefs_to_remove: List[int]
):
    """
    지정된 파일들에서 사용자가 선택한 워터마크를 제거하고 결과를 저장합니다.

    Args:
        file_paths (List[str]): 처리할 원본 PDF 파일 경로 리스트.
        output_dir (str): 결과 파일을 저장할 폴더 경로.
        xrefs_to_remove (List[int]): 사용자가 GUI에서 선택한, 제거할 이미지의 xref 리스트.
    """
    output_path = Path(output_dir)
    if not output_path.is_dir():
        print(f"오류: 출력 디렉토리 '{output_dir}'를 찾을 수 없습니다.")
        return

    for file_path in file_paths:
        try:
            doc = fitz.open(file_path)
            
            # editor 모듈을 사용해 실제 워터마크 제거 작업 수행
            editor.remove_watermarks_by_xrefs(doc, xrefs_to_remove)
            
            # 결과 저장
            output_filename = output_path / f"{Path(file_path).stem}_removed.pdf"
            # garbage=4: 사용되지 않는 모든 객체를 정리 (가장 강력한 옵션)
            # deflate=True: 압축하여 파일 크기 최적화
            doc.save(str(output_filename), garbage=4, deflate=True)
            doc.close()
            print(f"'{output_filename}' 저장 완료.")

        except Exception as e:
            print(f"파일 처리 중 오류 발생 ({Path(file_path).name}): {e}")
            if 'doc' in locals() and doc.is_open:
                doc.close()
            continue

