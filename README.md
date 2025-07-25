# Contract Processing Script

This script is designed to automate the extraction of specific data points from large PDF contract documents. It identifies relevant pages, sends them to a Large Language Model (LLM) for analysis, and saves the structured data into a CSV file.

### Key Stages of the Process:

1.  **Page Identification (Efficiency Boost):**
    *   Instead of processing the entire (often large) PDF, the script first performs a high-speed scan to find "important pages."
    *   It uses multi-threading to concurrently search for specific keywords and section headers (e.g., "Agreement is entered into", "SCHEDULE J", "ARTICLE 19") that indicate the presence of key information.
    *   It has a fallback to Optical Character Recognition (OCR) for pages where text is not easily extractable.

2.  **Creating a "Short PDF":**
    *   Once the important page numbers are identified, the script creates a new, much smaller PDF (`_short.pdf`) containing only these relevant pages.
    *   This is a crucial optimization that reduces the amount of data sent to the LLM, making the process faster and more cost-effective.

3.  **Data Extraction with LLM:**
    *   The shortened PDF is sent to the Gemini Pro Vision model.
    *   The script dynamically builds a detailed prompt, instructing the LLM on exactly which fields to extract. These fields are cleverly loaded from an external `CCMS_Project_fields.csv` file, making the script highly configurable without needing code changes.
    *   It asks the LLM to return the data in a structured JSON format.

4.  **Data Processing and Enrichment:**
    *   The script parses the JSON response from the LLM.
    *   It performs post-processing, such as calculating the project's "End Date" based on the extracted "Start Date" and "Project Duration."
    *   It handles potentially nested data, like a "Location" field, and flattens it into separate columns for the final CSV ("Location - State", "Location - District", etc.).

5.  **Output Generation:**
    *   The final, structured data for each contract is appended as a new row to the `extracted_contract_data.csv` file.
    *   The script saves progress incrementally, so if it's interrupted, the work already done is not lost.

### Overall Design:

*   **Modular:** The code is well-organized into clear, single-purpose functions (e.g., `find_important_pages`, `create_short_pdf`, `extract_data_with_llm`).
*   **Efficient:** The use of multi-threading for scanning and the creation of a short PDF are smart optimizations.
*   **Configurable:** Defining the extraction fields in an external CSV file is an excellent design choice that makes the tool flexible and easy to adapt.
*   **Robust:** It includes error handling for API calls, file operations, and JSON parsing, and even retries with OCR, making it resilient to common issues.
