import sys
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract

def debug_pdf_pages(pdf_path, page_numbers):
    """
    Extracts and prints text from specific pages of a PDF for debugging.
    """
    reader = PdfReader(pdf_path)
    print(f"--- Debugging {pdf_path} ---")
    for page_num in page_numbers:
        if page_num - 1 >= len(reader.pages):
            print(f"\n--- Page {page_num}: Not found (PDF only has {len(reader.pages)} pages) ---")
            continue

        print(f"\n--- Extracting text from page {page_num} ---")
        page = reader.pages[page_num - 1]
        text = page.extract_text()

        # Fallback to OCR if text is sparse
        if not text or len(text.strip()) < 50:
            print("(No text found, falling back to OCR...)")
            try:
                images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
                if images:
                    text = pytesseract.image_to_string(images[0])
            except Exception as ocr_error:
                print(f"OCR Error on page {page_num}: {ocr_error}")
                text = "[OCR FAILED]"
        
        print(text)
    print("\n--- Debugging complete ---")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debug_pages.py <pdf_file> <page1> <page2> ...")
    else:
        pdf_file = sys.argv[1]
        pages = [int(p) for p in sys.argv[2:]]
        debug_pdf_pages(pdf_file, pages)
