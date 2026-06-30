# 💼 FinAI — AI-Powered Expense Tracker

Built with Streamlit + Google Gemini 2.5 Flash + SQLite.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 3. Run the app

```bash
streamlit run app.py
```

## Project Structure

```
finai/
├── app.py                    # Main dashboard
├── pages/
│   ├── upload.py             # Receipt upload & Gemini extraction
│   ├── expense_history.py    # Browse, edit, delete expenses
│   ├── analytics.py          # Charts + AI insights
│   └── settings.py           # Health checks & DB management
├── utils/
│   ├── gemini_client.py      # Gemini SDK layer
│   ├── database.py           # SQLite CRUD
│   ├── image_utils.py        # Pillow preprocessing
│   ├── pdf_utils.py          # PDF → text or images
│   ├── text_utils.py         # TXT file reader
│   ├── prompts.py            # System instructions & user prompts
│   └── schema.py             # Pydantic response schemas
├── assets/
│   └── styles.css            # Custom CSS
├── requirements.txt

```

## Supported Input Types

| Type | Processing |
|------|-----------|
| PNG / JPG / JPEG / WEBP | Pillow preprocessing → Gemini Vision |
| PDF (searchable) | pypdf text extraction → Gemini |
| PDF (scanned) | PyMuPDF page images → Gemini Vision |
| TXT | Direct text → Gemini |
| Pasted text | Direct text → Gemini |
