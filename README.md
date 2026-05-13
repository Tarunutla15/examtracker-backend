## ExamTracker OCR Backend

This backend is now split into a cleaner app structure for LLM-based exam extraction:

```text
backend/
  app/
    api/routes/
    core/
    prompts/
    schemas/
    services/
    utils/
  main.py
  requirements.txt
  .env.example
```

### Current flow

1. Uploaded image/PDF files are sent to OpenAI for raw document text extraction.
2. The extracted text is then passed into an LLM structuring step.
3. The structuring step returns strict JSON mapped to the selected exam sections.

### Install

```bash
pip install -r requirements.txt
```

### Environment

Copy `.env.example` to `.env` and fill in your OpenAI key.

### Run

```bash
python main.py
```

The API starts on `http://127.0.0.1:8001` by default.
