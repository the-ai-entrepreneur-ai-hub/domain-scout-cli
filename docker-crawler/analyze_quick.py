import csv
import re

def analyze_results(file_path):
    total = 0
    success_counts = {
        'company_name': 0, 'street': 0, 'postal_code': 0, 'city': 0,
        'legal_form': 0, 'emails': 0, 'phone_numbers': 0, 'ceo_names': 0
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if len(row.get('company_name', '') or '') > 2: success_counts['company_name'] += 1
                if len(row.get('street', '') or '') > 3: success_counts['street'] += 1
                if len(row.get('postal_code', '') or '') > 3: success_counts['postal_code'] += 1
                if len(row.get('city', '') or '') > 2: success_counts['city'] += 1
                if len(row.get('legal_form', '') or '') > 1: success_counts['legal_form'] += 1
                if len(row.get('emails', '') or '') > 5: success_counts['emails'] += 1
                if len(row.get('phone_numbers', '') or '') > 5: success_counts['phone_numbers'] += 1
                if len(row.get('ceo_names', '') or '') > 3: success_counts['ceo_names'] += 1
                
    except FileNotFoundError:
        print("Results file not found.")
        return

    print(f"Total Records: {total}")
    for field, count in success_counts.items():
        print(f"{field}: {count} ({count/total*100:.1f}%)")

if __name__ == "__main__":
    analyze_results('D:/docker-crawler/data/results.csv')
