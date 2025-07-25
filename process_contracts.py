import os
import re
import time
import base64
import pandas as pd
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_path
import pytesseract
import concurrent.futures
import json
from datetime import datetime, timedelta

# Configure Google Gemini API
# It's recommended to set GOOGLE_API_KEY as an environment variable
# genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Global search terms for efficiency
SEARCH_TERMS = {
    "(?:This\s+)?Agreement\s+is\s+entered\s+into": 0,
    "(?:\n|^)\s*SCHEDULE\s*[- ]*\s*J\s*(?:\n|$)": re.MULTILINE,
    "(?:\n|^)\s*ARTICLE\s+19\s*(?:\n|$)": re.MULTILINE,
    "(?:\n|^)\s*SCHEDULE\s*[- ]*\s*H\s*(?:\n|$)": re.MULTILINE,
}

def _process_page_chunk(pdf_path, start_page_idx, end_page_idx):
    """
    Helper function to process a chunk of pages in a separate thread.
    Returns a set of important page numbers found in this chunk.
    """
    local_important_pages = set()
    reader = PdfReader(pdf_path) # Open reader in each thread for thread-safety

    for page_num in range(start_page_idx, end_page_idx):
        if page_num >= len(reader.pages):
            break

        page = reader.pages[page_num]
        text = page.extract_text()

        # Fallback to OCR if text is sparse
        if not text or len(text.strip()) < 50:
            try:
                images = convert_from_path(pdf_path, first_page=page_num + 1, last_page=page_num + 1)
                if images:
                    text = pytesseract.image_to_string(images[0])
            except Exception as ocr_error:
                print(f"Could not process page {page_num + 1} with OCR in chunk: {ocr_error}") # Re-enabled for debugging
                text = ""

        # Check for search terms
        for term in SEARCH_TERMS:
            if re.search(term, text, re.IGNORECASE):
                local_important_pages.add(page_num)
                if page_num + 1 < len(reader.pages):
                    local_important_pages.add(page_num + 1)
                print(f"  - Found '{term}' on page {page_num + 1}. Adding pages {page_num + 1} and {page_num + 2}.") # Re-enabled for debugging

    return local_important_pages

def find_important_pages(pdf_path, chunk_size=50):
    """
    Scans a PDF to find pages containing specific keywords using multi-threading.
    Returns a sorted, unique list of page numbers to keep.
    """
    important_pages = {0, 1}  # Always include the first two pages
    reader = PdfReader(pdf_path)
    num_pages = len(reader.pages)
    print(f"  Scanning {num_pages} pages using {os.cpu_count()} threads...")

    # Create chunks of pages for parallel processing
    page_chunks = []
    for i in range(0, num_pages, chunk_size):
        page_chunks.append((i, min(i + chunk_size, num_pages)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        future_to_chunk = {
            executor.submit(_process_page_chunk, pdf_path, start, end):
            (start, end) for start, end in page_chunks
        }

        for future in concurrent.futures.as_completed(future_to_chunk):
            try:
                chunk_important_pages = future.result()
                important_pages.update(chunk_important_pages)
            except Exception as exc:
                print(f"\n  Chunk processing generated an exception: {exc}")

    print("\n  Finished scanning.")
    return sorted(list(important_pages))

def create_short_pdf(pdf_path, page_numbers):
    """
    Creates a new PDF containing only the specified page numbers.
    """
    short_filename = os.path.splitext(pdf_path)[0] + "_short.pdf"
    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page_num in page_numbers:
            if page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])

        with open(short_filename, "wb") as f:
            writer.write(f)
        print(f"  - Successfully created short PDF: {short_filename}")
        return short_filename
    except Exception as e:
        print(f"Error creating short PDF for {pdf_path}: {e}")
        return None

def extract_data_with_llm(pdf_path, prompt):
    """
    Sends a PDF to a Google LLM (Gemini Pro Vision) for data extraction.
    Returns the LLM's response as a string.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY environment variable not set. Cannot use LLM.")
        return "LLM Error: API Key not set"

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    print("  - Gemini API configured.") # Added for debugging

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        # Encode PDF to base64 for multimodal input
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Construct the content for the LLM
        contents = [
            prompt,
            {
                "mime_type": "application/pdf",
                "data": pdf_base64
            }
        ]

        print(f"  - Sending {os.path.basename(pdf_path)} to LLM...")
        response = model.generate_content(contents)
        
        # Assuming the LLM returns text directly
        return response.text

    except Exception as e:
        print(f"Error during LLM extraction for {pdf_path}: {e}")
        return f"LLM Error: {e}"

def calculate_end_date(start_date_str, duration_str):
    """
    Calculates the end date based on a start date string and a duration string.
    Handles durations in days or months.
    """
    try:
        # Parse start date
        start_date = datetime.strptime(start_date_str, "%B %d, %Y") # e.g., October 15, 2018
    except ValueError:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d") # Another common format
        except ValueError:
            return "Invalid Start Date Format"

    # Parse duration
    duration_match = re.match(r"(\d+)\s*(day|month)s?", duration_str, re.IGNORECASE)
    if duration_match:
        value = int(duration_match.group(1))
        unit = duration_match.group(2).lower()

        if unit == "day":
            end_date = start_date + timedelta(days=value)
        elif unit == "month":
            # For months, add to year and month, then adjust day if necessary
            year = start_date.year + value // 12
            month = start_date.month + value % 12
            if month > 12:
                year += 1
                month -= 12
            # Handle cases where day is greater than days in new month
            day = min(start_date.day, (datetime(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31)
            end_date = datetime(year, month, day)
        else:
            return "Invalid Duration Unit"
        
        return end_date.strftime("%Y-%m-%d")
    else:
        return "Invalid Duration Format"

def process_contract(contract_pdf_file, llm_prompt_fields, output_columns):
    """
    Processes a single PDF contract file to create a shortened version
    containing only important pages, then extracts data using an LLM.
    Returns a dictionary of extracted data, or None if an error occurs.
    """
    print(f"Processing {contract_pdf_file}...")
    start_time = time.time()
    extracted_data = {}
    short_pdf_path = None

    try:
        short_pdf_path = os.path.splitext(contract_pdf_file)[0] + "_short.pdf"
        if os.path.exists(short_pdf_path) and os.path.getsize(short_pdf_path) > 0:
            print(f"  - Reusing existing short PDF: {short_pdf_path}")
        else:
            # Step 1: Create short PDF
            pages_to_keep = find_important_pages(contract_pdf_file)
            print(f"  - Identified {len(pages_to_keep)} important pages: {[p + 1 for p in pages_to_keep]}")
            short_pdf_path = create_short_pdf(contract_pdf_file, pages_to_keep)

        print(f"  - Short PDF path: {short_pdf_path}") # Added for debugging
        if short_pdf_path:
            # Step 2: Construct LLM prompt dynamically
            llm_prompt = (
                "From the provided contract PDF, extract the following information:"
            )
            for field_name, description in llm_prompt_fields.items():
                llm_prompt += f"- {field_name} ({description})"
            llm_prompt += "\nFormat the output as a JSON object with keys matching the field names exactly."

            print(f"  - LLM Prompt:\n---\n{llm_prompt}\n---") # Print full LLM prompt
            print(f"  - Sending {os.path.basename(short_pdf_path)} to LLM for extraction...")
            llm_response = extract_data_with_llm(short_pdf_path, llm_prompt)
            print(f"  - LLM Raw Response:\n---\n{llm_response}\n---") # Print full LLM response

            # Attempt to parse LLM response as JSON
            try:
                # Strip markdown code block fences if present
                if llm_response.startswith("```json") and llm_response.endswith("```"):
                    llm_response = llm_response[len("```json"): -len("```")].strip()
                extracted_data = json.loads(llm_response)
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse LLM response as JSON: {e}")
                extracted_data["LLM_Raw_Response"] = llm_response # Store raw response for debugging

            # Calculate End Date if Start Date and Project Duration are available
            start_date = extracted_data.get("Start Date")
            project_duration = extracted_data.get("Project Duration")
            if start_date and project_duration:
                calculated_end_date = calculate_end_date(start_date, project_duration)
                extracted_data["End Date"] = calculated_end_date
            else:
                extracted_data["End Date"] = "Not Found"

    except Exception as e:
        print(f"An error occurred while processing {contract_pdf_file}: {e}")
    finally:
        end_time = time.time()
        print(f"  - Total processing time for {contract_pdf_file}: {end_time - start_time:.2f} seconds")
        # Clean up the short PDF if you don't need it after extraction
        # if short_pdf_path and os.path.exists(short_pdf_path):
        #     os.remove(short_pdf_path)
    return extracted_data

def main():
    """
    Main function to process all PDF contracts in the directory.
    Demonstrates usage of process_contract function and saves results to CSV.
    """
    output_csv_file = "extracted_contract_data.csv"
    
    # Read the project fields from the new CSV file
    try:
        project_fields_df = pd.read_csv("CCMS_Project_fields.csv")
        # Prepare fields for LLM prompt
        llm_prompt_fields = {}
        for index, row in project_fields_df.iterrows():
            field_name = row['Field Name']
            description = row['Description / Example']
            llm_prompt_fields[field_name] = description

        # Define output columns explicitly, with 'File Name' first
        output_columns = ["File Name"] + project_fields_df['Field Name'].tolist()
        
        # Handle Location field expansion for CSV output
        if "Location" in output_columns:
            output_columns.remove("Location")
            output_columns.extend(["Location - State", "Location - District", "Location - Towns covered"])

        # Ensure End Date is in output columns, even if not directly from LLM
        if "End Date" not in output_columns:
            output_columns.insert(output_columns.index("Project Duration") + 1, "End Date")

    except FileNotFoundError:
        print("Error: 'CCMS_Project_fields.csv' not found. Using fallback fields.")
        llm_prompt_fields = {
            "Name of the Authority": "Party 1",
            "Name of the Contractor": "Party 2",
            "Project Name": "",
            "Start Date": "Agreement Date",
            "Project Duration": "Duration of the project from Schedule J (e.g., '730 days', '24 months')",
            "Contract Value": "from Article 19",
            "Payment Schedule": "from Schedule H",
            "Location": "State, District, Towns covered", # Keep as single field for LLM, flatten later
            "Project Milestones List": "List all project milestones from Schedule J as a comma-separated list.",
        }
        output_columns = [
            "File Name", "Name of the Authority", "Name of the Contractor",
            "Project Name", "Start Date", "Project Duration", "End Date",
            "Contract Value", "Payment Schedule",
            "Location - State", "Location - District", "Location - Towns covered",
            "Project Milestones List"
        ]

    # Write header to CSV file
    pd.DataFrame(columns=output_columns).to_csv(output_csv_file, mode='a', index=False)

    pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf') and not f.lower().endswith('_short.pdf')]

    if not pdf_files:
        print("No original PDF files found to process.")
        return

    print("Starting batch processing of PDF files...")
    for pdf_file in pdf_files:
        extracted_data = process_contract(pdf_file, llm_prompt_fields, output_columns)
        if extracted_data:
            # Prepare row_data for CSV, handling nested Location and nulls
            row_data = {}
            for col in output_columns:
                if col == "Contract Value (₹ Cr)":
                    row_data[col] = extracted_data.get("Contract Value", "")
                elif col == "Project Milestones List":
                    # LLM should return a paragraph summary, so just assign
                    row_data[col] = extracted_data.get(col, "")
                elif col == "Payment Schedule":
                    # LLM should return a paragraph summary, so just assign
                    row_data[col] = extracted_data.get(col, "")
                else:
                    value = extracted_data.get(col, "")
                    row_data[col] = value if value is not None else ""
            
            # Handle Location flattening
            if "Location" in extracted_data and isinstance(extracted_data["Location"], dict):
                location_data = extracted_data["Location"]
                row_data["Location - State"] = location_data.get("State", "")
                row_data["Location - District"] = location_data.get("District", "")
                row_data["Location - Towns covered"] = location_data.get("Towns covered", "")
            elif "Location" in extracted_data and isinstance(extracted_data["Location"], str):
                # If LLM returns Location as a string, try to parse it or keep as is
                row_data["Location - State"] = extracted_data["Location"]
                row_data["Location - District"] = ""
                row_data["Location - Towns covered"] = ""

            row_data["File Name"] = pdf_file # Ensure filename is always present
            
            # Remove the original 'Location' key if it exists and was flattened
            if "Location" in extracted_data:
                del extracted_data["Location"]

            pd.DataFrame([row_data]).to_csv(output_csv_file, mode='a', header=False, index=False)
            print(f"  - Data for {pdf_file} appended to {output_csv_file}")

    print(f"Script finished. Final data saved to {output_csv_file}")

if __name__ == "__main__":
    main()
