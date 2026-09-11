# VISTA Dataset Directory

This directory maps the medical datasets used across the VISTA system.

## Dataset Structure

The active hospital datasets are stored in `phase1_dataset/phase1_dataset/`:

1. **`Full_Medical_Data_Lake/`**
   - `admissions.csv` (5,000,000 admissions)
   - `billing.csv` (5,000,000 billing records)
   - `doctors.csv` (2,000 physicians across specialties)
   - `diseases.csv` (28 disease categories with ICD-10 codes)
   - `departments.csv` (21 hospital departments)
   - `unstructured_notes/` (18,100 clinical encounter discharge summaries)

2. **`medical_data_lake_bundle/`**
   - `combined_dataset.csv` (~52,350 clinical transcription notes from MTSamples across 40+ medical specialties)
   - `output/` (PDF report samples by medical specialty)

3. **`Reports/`**
   - 20 Patient and departmental diagnostic workups in `.pdf` and `.docx` format for OCR and multi-modal testing.

4. **`healthcare_dataset.csv`**
   - 1,000 baseline patient rows with clinical vitals.
