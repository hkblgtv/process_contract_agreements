import os
import re
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader

def extract_text_from_pdf(pdf_path, page_limit=100):
    """
    Extracts text from a PDF file, up to a specified page limit.
    Adds page break markers and uses OCR as a fallback.
    """
    text_content = []
    try:
        reader = PdfReader(pdf_path)
        num_pages = len(reader.pages)
        pages_to_process = min(num_pages, page_limit)
        print(f"  Total pages: {num_pages} (processing up to {pages_to_process})")
        for page_num in range(pages_to_process):
            print(f"  - Processing page {page_num + 1}/{pages_to_process}...", end='\r')
            page = reader.pages[page_num]
            page_text = page.extract_text()
            
            # Use OCR as a fallback
            if not page_text or not page_text.strip():
                try:
                    images = convert_from_path(pdf_path, first_page=page_num + 1, last_page=page_num + 1)
                    if images:
                        page_text = pytesseract.image_to_string(images[0])
                except Exception as ocr_error:
                    print(f"\nCould not process page {page_num + 1} with OCR: {ocr_error}")
                    page_text = "" # Ensure page_text is a string

            text_content.append(f"--- Page {page_num + 1} --- \n{page_text}")

        print(f"\n  Finished processing {pages_to_process} pages.")
    except Exception as e:
        print(f"\nError reading {pdf_path}: {e}")
    
    return "\n\n".join(text_content)

def find_agreement_details(text):
    """
    Finds the core agreement details from the e-stamp page.
    Looks for the 'This Agreement is entered into...' clause.
    """
    # Regex to find the block of text with the main agreement details
    match = re.search(r"This Agreement is entered into.*?BETWEEN(.*?)AND(.*?)(?:for the work of|on this)(.*?day of.*)", text, re.DOTALL | re.IGNORECASE)
    if match:
        party1 = ' '.join(match.group(1).strip().replace('\n', ' ').split())
        party2 = ' '.join(match.group(2).strip().replace('\n', ' ').split())
        agreement_date = ' '.join(match.group(3).strip().replace('\n', ' ').split())
        
        # A simplified project name search within the context of the agreement clause
        project_name_match = re.search(r"for the work of(.*?)(?:on EPC|.)", text, re.DOTALL | re.IGNORECASE)
        project_name = "Not Found"
        if project_name_match:
            project_name = ' '.join(project_name_match.group(1).strip().replace('\n', ' ').split())

        return party1, party2, agreement_date, project_name
    return "Not Found", "Not Found", "Not Found", "Not Found"

def find_schedule_j_details(text):
    """
    Extracts Completion Date and Milestones from Schedule J.
    """
    completion_date = "Not Found"
    milestones = "Not Found"
    
    # Find the text block for Schedule J
    schedule_j_match = re.search(r"SCHEDULE-J(.*?)(?:SCHEDULE-K|Signature Page)", text, re.DOTALL | re.IGNORECASE)
    if schedule_j_match:
        schedule_j_text = schedule_j_match.group(1)
        
        # Find Scheduled Completion Date
        date_match = re.search(r"Scheduled Completion Date.*?(\d+\s+days)", schedule_j_text, re.DOTALL | re.IGNORECASE)
        if date_match:
            completion_date = date_match.group(1).strip()
            
        # Find Project Milestones
        milestones_match = re.search(r"Project Milestone(.*?)Payment upon achievement", schedule_j_text, re.DOTALL | re.IGNORECASE)
        if milestones_match:
            milestones = milestones_match.group(1).strip().replace('\n', ' ')
            milestones = ' '.join(milestones.split())

    return completion_date, milestones

def find_contract_price(text):
    """
    Extracts the contract price from Article 19.
    """
    # Find the text block for Article 19
    article_19_match = re.search(r"ARTICLE 19\s+CONTRACT PRICE(.*?)(?:ARTICLE 20|Schedule H)", text, re.DOTALL | re.IGNORECASE)
    if article_19_match:
        article_19_text = article_19_match.group(1)
        price_match = re.search(r"Rs\.\s*([\d,]+\.?\d*)", article_19_text, re.IGNORECASE)
        if price_match:
            return f"Rs. {price_match.group(1).strip()}"
    return "Not Found"

def find_payment_schedule(text):
    """
    Extracts the payment schedule clauses from Schedule H.
    """
    # Find the text block for Schedule H
    schedule_h_match = re.search(r"SCHEDULE-H\s+PAYMENT SCHEDULE(.*?)(?:SCHEDULE-I|Annex-I)", text, re.DOTALL | re.IGNORECASE)
    if schedule_h_match:
        # Return the whole section for manual review
        payment_schedule = schedule_h_match.group(1).strip().replace('\n', ' ')
        return ' '.join(payment_schedule.split())
    return "Not Found"

def main():
    """
    Main function to process all PDF contracts in the directory.
    Saves extracted text and writes CSV data incrementally.
    """
    output_csv_file = "extracted_contract_data.csv"
    
    # Read the template to define the columns for our output
    try:
        template_df = pd.read_csv("CCMS_Project Setup Template_R0.csv")
        output_columns = template_df['Field Name'].tolist()
    except FileNotFoundError:
        print("Error: 'CCMS_Project Setup Template_R0.csv' not found.")
        output_columns = ["File Name", "Project Name", "Contract Value"] # Fallback

    # Write header to CSV file
    pd.DataFrame(columns=output_columns).to_csv(output_csv_file, index=False)

    # Find all PDF files in the current directory
    pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]

    for pdf_file in pdf_files:
        print(f"Processing {pdf_file}...")
        full_text = extract_text_from_pdf(pdf_file)

        # Save the extracted text to a file for review
        text_file_name = os.path.splitext(pdf_file)[0] + ".txt"
        with open(text_file_name, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"  - Extracted text saved to {text_file_name}")

        # --- Data Extraction using new, targeted functions ---
        print("  - Extracting agreement details...")
        party1, party2, agreement_date, project_name = find_agreement_details(full_text)
        
        print("  - Extracting Schedule J details...")
        end_date, milestones = find_schedule_j_details(full_text)
        
        print("  - Extracting contract price...")
        contract_price = find_contract_price(full_text)
        
        print("  - Extracting payment schedule...")
        payment_schedule = find_payment_schedule(full_text)

        data = {
            "File Name": pdf_file,
            "Name of the Authority": party1,
            "Name of the Contractor": party2,
            "Start Date": agreement_date, # Using agreement date as start date per instructions
            "Project Name": project_name,
            "End Date": end_date,
            "Milestones Defined?": milestones,
            "Contract Value (₹ Cr)": contract_price,
            "Payment Schedule": payment_schedule,
        }
        
        # Append the extracted data to the CSV file
        row_data = {col: data.get(col, "") for col in output_columns}
        pd.DataFrame([row_data]).to_csv(output_csv_file, mode='a', header=False, index=False)
        print(f"  - Data for {pdf_file} appended to {output_csv_file}")

    print(f"\nProcessing complete. Final data saved to {output_csv_file}")

if __name__ == "__main__":
    main()
