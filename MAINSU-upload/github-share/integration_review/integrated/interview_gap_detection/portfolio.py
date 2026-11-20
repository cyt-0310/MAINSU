"""讀取備審 PDF 文字。"""
import os
from typing import Optional

from pypdf import PdfReader


def find_portfolio_pdf(search_dirs) -> Optional[str]:
    """在指定資料夾中找備審 PDF，檔名含『輔大資管』者優先。"""
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        pdf_files = sorted(f for f in os.listdir(d) if f.endswith(".pdf"))
        for f in pdf_files:
            if "輔大資管" in f:
                return os.path.join(d, f)
        if pdf_files:
            return os.path.join(d, pdf_files[0])
    return None


def load_portfolio_pdf(pdf_path: Optional[str]) -> dict:
    if pdf_path and os.path.exists(pdf_path):
        print(f"📂 成功抓取備審 PDF 檔案: {os.path.basename(pdf_path)}")
        try:
            reader = PdfReader(pdf_path)
            extracted_text = ""
            for page in reader.pages:
                extracted_text += (page.extract_text() or "") + "\n"
            name = os.path.basename(pdf_path)
            return {
                "student_name": name.replace(".pdf", ""),
                "full_text": extracted_text,
                "pdf_name": name
            }
        except Exception as e:
            print(f"⚠️ 讀取 PDF 時發生錯誤: {e}")

    print("⚠️ 找不到備審 PDF，改用內建測試文字。")
    return {
        "student_name": "測試學生",
        "full_text": "熱舞社 幹部 舞研 指導 溝通 對接 專題 系統 開發",
        "pdf_name": "None"
    }
