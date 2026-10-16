
# InvoicePilot AI 🧾

A privacy-first invoice assistant built with Streamlit and a locally running Ollama model.

## Features

- Extract invoice fields from pasted text.
- Upload text-based PDF and TXT invoices.
- Identify potentially overdue invoices.
- View a session-based invoice dashboard and history.
- Detect duplicate vendor and invoice-number combinations.
- Download individual invoice details as JSON.
- Export invoice history as CSV.

## Tech Stack

- Python
- Streamlit
- Ollama
- Llama 3.2 3B
- pypdf

## Requirements

- Python installed on your computer
- Ollama installed and running
- The `llama3.2:3b` model downloaded locally

## Setup

1. Clone or download this repository.
2. Open the project folder in a terminal.
3. Install the Python dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Download the model if needed:

   ```bash
   ollama pull llama3.2:3b
   ```

5. Start Ollama if it is not already running:

   ```bash
   ollama serve
   ```

6. Start the app in another terminal:

   ```bash
   python -m streamlit run app.py
   ```

## Privacy and Limitations

Invoice analysis uses a locally running Ollama model. Invoice history is kept in Streamlit session state and is not intentionally stored in a database.

AI-generated fields can be incorrect. Verify amounts, currencies, invoice numbers, and dates against the original document. Scanned PDFs may need OCR, which is not currently included.

## License

See the LICENSE file.
