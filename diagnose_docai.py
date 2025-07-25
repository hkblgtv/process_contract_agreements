import os
from google.cloud import documentai_v1beta3 as documentai

# --- Configuration ---
# Your Google Cloud project ID
PROJECT_ID = "dynamic-aurora-467007-q5"
# The location of your Document AI processor (e.g., 'us')
LOCATION = "us"
# The ID of your Document AI processor
PROCESSOR_ID = "246e93e080df365"
PROCESSOR_ID = "c649821a479ca9b"  # document ocr
# The path to a small PDF file to test with
PDF_PATH = "KAR-WAL_NH4 (Lot 5 to 20)_short.pdf"

def diagnose_docai():
    """
    A simple function to diagnose Document AI connection and permissions.
    """
    print("--- Starting Document AI Diagnosis ---")

    # 1. Check for credentials
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Error: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        return
    print(f"Using credentials from: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")

    # 2. Check if the PDF file exists
    if not os.path.exists(PDF_PATH):
        print(f"Error: Test PDF file not found at '{PDF_PATH}'")
        return
    print(f"Found test PDF: {PDF_PATH}")

    try:
        # 3. Instantiate a client
        print("Connecting to Document AI...")
        client = documentai.DocumentProcessorServiceClient()

        # 4. Construct the full processor name
        name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
        print(f"Processor name: {name}")

        # 5. Read the file into memory
        with open(PDF_PATH, "rb") as image:
            image_content = image.read()

        # 6. Create the Document AI request object
        raw_document = documentai.RawDocument(
            content=image_content, mime_type="application/pdf"
        )
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)

        # 7. Process the document
        print("Sending request to Document AI processor...")
        result = client.process_document(request=request)

        # 8. If successful, print the extracted text
        print("\n--- Diagnosis Successful! ---")
        print("Extracted text:")
        print(result.document.text)

    except Exception as e:
        print("\n--- Diagnosis Failed ---")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    diagnose_docai()
