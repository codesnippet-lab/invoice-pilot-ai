
import csv
import io
import json
from datetime import date
from io import BytesIO

import requests
import streamlit as st
from pypdf import PdfReader

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"

st.set_page_config(
    page_title="InvoicePilot AI",
    page_icon="🧾",
    layout="wide",
)

# ---------- Session state ----------
if "invoices" not in st.session_state:
    st.session_state.invoices = []

if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ---------- Page header ----------
st.title("🧾 InvoicePilot AI")
st.caption("Your local AI assistant for understanding invoices")

st.info(
    "AI runs through Ollama on your computer. "
    "Check extracted information against the original invoice."
)


# ---------- File reading ----------
def read_uploaded_file(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith(".txt"):
        return uploaded_file.getvalue().decode(
            "utf-8", errors="replace"
        )

    if filename.endswith(".pdf"):
        reader = PdfReader(BytesIO(uploaded_file.getvalue()))
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    raise ValueError("Please upload a PDF or TXT file.")


# ---------- AI extraction ----------
def analyze_invoice(invoice_text):
    prompt = f"""
Extract the invoice details from the text below.

Return a JSON object with these exact keys:
vendor, invoice_number, invoice_date, due_date,
currency, total, category, missing_fields, notes.

Rules:
- Use null for unknown values.
- Never invent dates, amounts, or names.
- Keep total as a number or a short numeric string.
- missing_fields must be a list of missing field names.
- notes must be a short string.
- Do not include markdown fences.

Invoice text:
{invoice_text}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=180,
    )
    response.raise_for_status()

    result = json.loads(response.json()["response"])

    if not isinstance(result, dict):
        raise ValueError("The AI returned an invalid result.")

    required_keys = [
        "vendor",
        "invoice_number",
        "invoice_date",
        "due_date",
        "currency",
        "total",
        "category",
        "missing_fields",
        "notes",
    ]

    for key in required_keys:
        result.setdefault(key, None)

    if not isinstance(result["missing_fields"], list):
        result["missing_fields"] = []

    return result


# ---------- Helpers ----------
def due_status(due_date):
    if not due_date:
        return "Unknown"

    try:
        parsed = date.fromisoformat(str(due_date)[:10])
    except ValueError:
        return "Check date"

    if parsed < date.today():
        return "Overdue"
    if parsed == date.today():
        return "Due today"
    return "Upcoming"


def parse_total(value):
    """Convert a simple invoice amount to a number for dashboard totals."""
    if value is None:
        return None

    try:
        cleaned = str(value).replace(",", "").strip()
        cleaned = cleaned.replace("₹", "").replace("$", "")
        cleaned = cleaned.replace("€", "").replace("£", "")
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def already_added(result):
    vendor = str(result.get("vendor") or "").strip().casefold()
    number = str(result.get("invoice_number") or "").strip().casefold()

    # Avoid treating missing invoice numbers as duplicates.
    if not vendor or not number:
        return False

    for invoice in st.session_state.invoices:
        old_vendor = str(invoice.get("vendor") or "").strip().casefold()
        old_number = str(
            invoice.get("invoice_number") or ""
        ).strip().casefold()

        if vendor == old_vendor and number == old_number:
            return True

    return False


def make_csv(invoices):
    output = io.StringIO()

    columns = [
        "vendor",
        "invoice_number",
        "invoice_date",
        "due_date",
        "currency",
        "total",
        "category",
        "status",
        "notes",
    ]

    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()

    for invoice in invoices:
        row = {key: invoice.get(key) for key in columns}
        row["status"] = due_status(invoice.get("due_date"))
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")


# ---------- Dashboard ----------
st.subheader("📊 Dashboard")

invoices = st.session_state.invoices
numeric_totals = [
    parse_total(invoice.get("total"))
    for invoice in invoices
]
numeric_totals = [
    value for value in numeric_totals if value is not None
]

overdue_count = sum(
    due_status(invoice.get("due_date")) == "Overdue"
    for invoice in invoices
)

col1, col2, col3 = st.columns(3)
col1.metric("Invoices analyzed", len(invoices))
col2.metric("Overdue invoices", overdue_count)
col3.metric(
    "Sum of extracted amounts",
    f"{sum(numeric_totals):,.2f}" if numeric_totals else "—",
)

st.caption(
    "The sum includes amounts the app can interpret as numbers. "
    "It may combine different currencies, so check each currency before "
    "using this figure as a financial total."
)

st.divider()

# ---------- Invoice analyzer ----------
st.subheader("🔎 Analyze an invoice")

tab_text, tab_file = st.tabs(
    ["Paste invoice text", "Upload PDF or TXT"]
)

with tab_text:
    invoice_text = st.text_area(
        "Invoice text",
        height=200,
        placeholder=(
            "Vendor: ABC Supplies\n"
            "Invoice Number: INV-101\n"
            "Invoice Date: 2026-10-10\n"
            "Due Date: 2026-10-12\n"
            "Currency: INR\n"
            "Total: 2500"
        ),
    )
    analyze_text_clicked = st.button(
        "Analyze text",
        type="primary",
    )

with tab_file:
    uploaded_file = st.file_uploader(
        "Choose a PDF or TXT invoice",
        type=["pdf", "txt"],
    )
    analyze_file_clicked = st.button(
        "Analyze uploaded file",
        type="primary",
    )

text_to_analyze = None

if analyze_text_clicked:
    text_to_analyze = invoice_text

if analyze_file_clicked:
    if uploaded_file is None:
        st.warning("Choose a file first.")
    else:
        try:
            text_to_analyze = read_uploaded_file(uploaded_file)
            if not text_to_analyze.strip():
                st.warning(
                    "No readable text was found. "
                    "Scanned PDFs may require OCR."
                )
                text_to_analyze = None
        except Exception as error:
            st.error(f"Could not read the file: {error}")

if text_to_analyze is not None:
    if not text_to_analyze.strip():
        st.warning("Enter some invoice text first.")
    else:
        try:
            with st.spinner("Analyzing with your local AI..."):
                result = analyze_invoice(text_to_analyze)

            st.session_state.last_result = result

            st.success("Invoice analysis complete!")

            if already_added(result):
                st.warning(
                    "This vendor and invoice number already exist "
                    "in your history. The duplicate was not added."
                )
            else:
                st.session_state.invoices.append(result)
                st.success("Invoice added to this session's history.")

        except requests.exceptions.ConnectionError:
            st.error(
                "Cannot connect to Ollama. Make sure Ollama is running."
            )
        except requests.exceptions.Timeout:
            st.error("The AI took too long to respond. Try again.")
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            st.error(f"Analysis failed: {error}")

# ---------- Latest analysis ----------
if st.session_state.last_result:
    result = st.session_state.last_result

    st.divider()
    st.subheader("📄 Latest invoice result")

    col1, col2, col3 = st.columns(3)
    col1.metric("Vendor", str(result.get("vendor") or "Unknown"))
    col2.metric(
        "Invoice number",
        str(result.get("invoice_number") or "Unknown"),
    )
    col3.metric(
        "Total",
        f"{result.get('currency') or ''} "
        f"{result.get('total') if result.get('total') is not None else 'Unknown'}",
    )

    st.write("**Invoice date:**", result.get("invoice_date") or "Unknown")
    st.write("**Due date:**", result.get("due_date") or "Unknown")
    st.write("**Category:**", result.get("category") or "Unknown")

    status = due_status(result.get("due_date"))

    if status == "Overdue":
        st.error("⚠️ This invoice appears to be overdue.")
    elif status == "Due today":
        st.warning("This invoice is due today.")
    elif status == "Upcoming":
        st.success("This invoice is not overdue.")
    else:
        st.warning("Due date is unknown or needs checking.")

    missing = result.get("missing_fields") or []
    if missing:
        st.warning("Review missing fields: " + ", ".join(map(str, missing)))

    st.write("**AI notes:**", result.get("notes") or "None")
    st.json(result)

    st.download_button(
        "Download latest invoice as JSON",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="invoice_details.json",
        mime="application/json",
    )

# ---------- Invoice history ----------
st.divider()
st.subheader("🗂️ Invoice history")

if st.session_state.invoices:
    st.dataframe(
        [
            {
                "Vendor": invoice.get("vendor") or "Unknown",
                "Invoice number": invoice.get("invoice_number") or "Unknown",
                "Date": invoice.get("invoice_date") or "Unknown",
                "Due date": invoice.get("due_date") or "Unknown",
                "Currency": invoice.get("currency") or "",
                "Total": invoice.get("total") or "",
                "Status": due_status(invoice.get("due_date")),
            }
            for invoice in st.session_state.invoices
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "⬇️ Export invoice history as CSV",
        data=make_csv(st.session_state.invoices),
        file_name="invoice_history.csv",
        mime="text/csv",
    )

    if st.button("Clear session history"):
        st.session_state.invoices = []
        st.session_state.last_result = None
        st.rerun()
else:
    st.write("No invoices in this session yet. Analyze one above to begin.")

st.caption(
    "Privacy note: invoice history is kept in Streamlit session state, "
    "not intentionally saved to a database. AI processing uses your local "
    "Ollama service. Verify extracted values before relying on them."
)
