# Backend - Work Recording Flask Application

This is the Flask backend for the Work Recording system. It handles PDF generation and data retrieval from Google Sheets.

## Installation

1. Create a Python virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
- **Windows**: `venv\Scripts\activate`
- **macOS/Linux**: `source venv/bin/activate`

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` with your Google Sheets configuration:
```
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_SHEET_GID=your_sheet_gid
DELIVERY_GOOGLE_SHEET_GID=your_delivery_sheet_gid
```

## Running the Application

```bash
python app.py
```

The application will start at `http://127.0.0.1:5000`

The Flask app also serves the frontend files from the project root, so the same server handles both the web forms and report/PDF pages.

## Running on Render

Use the root-level `render.yaml` from this repository. Render will install dependencies from `backend/requirements.txt` and start the app with:

```bash
gunicorn --bind 0.0.0.0:$PORT --chdir backend app:app
```

Set these environment variables in the Render Dashboard:

```text
GOOGLE_CSV_URL
GOOGLE_SHEET_ID
GOOGLE_SHEET_GID
DELIVERY_GOOGLE_CSV_URL
DELIVERY_GOOGLE_SHEET_GID
```

## Endpoints

### Withdraw
- `/withdraw` - Display withdraw records list
- `/withdraw/form/set/<set_no>` - Display form for specific withdraw record
- `/withdraw/preview_pdf` - Generate withdraw PDF (POST)

### Delivery
- `/delivery` - Display delivery records list
- `/delivery/form/<set_no>` - Display form for specific delivery record
- `/delivery/preview_pdf` - Generate delivery PDF (POST)

## Project Structure

```
backend/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .env                  # Environment variables (create from .env.example)
├── templates/
│   ├── withdraw_index.html
│   ├── withdraw_form.html
│   ├── withdraw_pdf.html
│   ├── delivery_index.html
│   ├── delivery_form.html
│   └── delivery_pdf.html
└── static/
    └── formstyle.css
```

## Requirements

- Python 3.7+
- Google Sheets API access
- Chrome or Edge browser (for PDF generation)
