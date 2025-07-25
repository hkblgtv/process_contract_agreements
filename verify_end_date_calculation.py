
import pandas as pd
from datetime import datetime, timedelta
import re
import os

def calculate_end_date(start_date_str, duration_str):
    """
    Calculates the end date based on a start date string and a duration string.
    Handles various date formats and durations in days or months.
    Outputs the date in DD-MM-YYYY format.
    """
    # Check for missing or non-string inputs
    if not isinstance(start_date_str, str) or not isinstance(duration_str, str):
        return "Invalid Input Type"

    start_date = None
    # Clean up the date string by removing ordinal suffixes (st, nd, rd, th) and commas
    cleaned_start_date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", start_date_str.replace(',', ''), flags=re.IGNORECASE).strip()

    # List of possible date formats
    date_formats = [
        "%d-%m-%Y",      # 29-12-2022
        "%d %B %Y",      # 16 March 2015
        "%B %Y",         # October 2018 (day will be 1)
        "%Y-%m-%d",      # 2022-12-29
    ]

    for fmt in date_formats:
        try:
            start_date = datetime.strptime(cleaned_start_date_str, fmt)
            # If the format is just month and year, default to the first day
            if "%d" not in fmt:
                start_date = start_date.replace(day=1)
            break  # Exit loop if parsing is successful
        except ValueError:
            continue

    if not start_date:
        return "Invalid Start Date Format"

    # Parse duration
    duration_match = re.search(r"(\d+)\s*(day|month)s?", duration_str, re.IGNORECASE)
    if duration_match:
        value = int(duration_match.group(1))
        unit = duration_match.group(2).lower()

        if unit == "day":
            end_date = start_date + timedelta(days=value)
        elif unit == "month":
            # Add months carefully
            total_months = start_date.month + value
            year = start_date.year + (total_months - 1) // 12
            month = (total_months - 1) % 12 + 1
            
            # Find the last day of the target month
            next_month = month + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year += 1
            last_day_of_month = (datetime(next_year, next_month, 1) - timedelta(days=1)).day
            
            day = min(start_date.day, last_day_of_month)
            end_date = datetime(year, month, day)
        else:
            return "Invalid Duration Unit"
        
        return end_date.strftime("%d-%m-%Y")
    else:
        return "Invalid Duration Format"

def verify_dates():
    """
    Reads the extracted data, recalculates the end date, and saves the verification results.
    """
    input_csv = "verify_end_date_data.csv"
    output_csv = "end_date_verification_results.csv"

    if not os.path.exists(input_csv):
        print(f"Error: Input file '{input_csv}' not found.")
        return

    try:
        df = pd.read_csv(input_csv, sep=',', engine='python')
    except pd.errors.ParserError as e:
        print(f"Error parsing CSV file: {e}")
        return
    
    # Ensure required columns exist
    if "Start Date" not in df.columns or "Project Duration" not in df.columns:
        print("Error: 'Start Date' or 'Project Duration' columns not found in the CSV.")
        return

    results = []
    for index, row in df.iterrows():
        start_date = row["Start Date"]
        duration = row["Project Duration"]
        calculated_end_date = calculate_end_date(start_date, duration)
        results.append({
            "Original Start Date": start_date,
            "Original Project Duration": duration,
            "Calculated End Date": calculated_end_date
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_csv, index=False)
    print(f"Verification complete. Results saved to '{output_csv}'")

if __name__ == "__main__":
    verify_dates()
