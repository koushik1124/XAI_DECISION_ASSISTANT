# app.py — FINAL version with File Support + Explainability Working Fully

from flask import Flask, render_template, request
from core_api import get_xai_prediction
import os, json, io, re
from datetime import datetime
import pandas as pd
import docx2txt
import fitz  # PyMuPDF

app = Flask(__name__)
os.makedirs("logs", exist_ok=True)


# ============================================================
# 1️⃣ File Extraction Helper
# ============================================================
def extract_file_text(uploaded_file):
    if not uploaded_file or uploaded_file.filename == "":
        return ""

    filename = uploaded_file.filename.lower()
    file_bytes = uploaded_file.read()

    try:
        if filename.endswith(".pdf"):
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            full_text = ""
            for page in pdf:
                full_text += page.get_text()
            return full_text

        elif filename.endswith((".doc", ".docx")):
            temp_path = "temp.docx"
            with open(temp_path, "wb") as temp:
                temp.write(file_bytes)
            text = docx2txt.process(temp_path)
            os.remove(temp_path)
            return text

        elif filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
            return df.to_string(index=False)

        elif filename.endswith((".xls", ".xlsx")):
            df = pd.read_excel(io.BytesIO(file_bytes))
            return df.to_string(index=False)

        elif filename.endswith(".txt"):
            return file_bytes.decode("utf-8", errors="ignore")

    except Exception as e:
        print("FILE PARSE ERROR:", e)
        return ""

    return ""


# ============================================================
# 2️⃣ Evidence Extraction
# ============================================================
def extract_evidence(factors, text):
    ev_list = []
    text_lower = text.lower()

    for f in factors:
        f_low = f.lower()
        idx = text_lower.find(f_low)
        if idx != -1:
            snippet = text[max(0, idx - 50): idx + len(f) + 50]
            ev_list.append({"factor": f, "snippet": snippet})

    return ev_list


# ============================================================
# 3️⃣ Bias / Fairness Detection
# ============================================================
def check_bias(text):
    sensitive_categories = {
        "Gender": ["male", "female", "man", "woman"],
        "Age": ["young", "old", "minor", "senior", "adult"],
        "Religion": ["hindu", "muslim", "christian", "sikh"],
        "Race": ["black", "white", "asian", "latino"]
    }

    findings = []
    lower_text = text.lower()

    for cat, words in sensitive_categories.items():
        for term in words:
            if re.search(rf"\b{term}\b", lower_text):
                findings.append({
                    "Category": cat,
                    "Term": term,
                    "Risk": "High"
                })

    return findings


# ============================================================
# 4️⃣ Flask Routes
# ============================================================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        uploaded_file = request.files.get("uploaded_file")

        extracted_text = extract_file_text(uploaded_file)

        # If user references PDF but no extraction found
        if ("pdf" in query.lower() or "document" in query.lower() or "file" in query.lower()) and not extracted_text:
            return render_template(
                "index.html",
                error="⚠ File upload detected but no text extracted! Try another document."
            )

        if not query and not extracted_text:
            return render_template(
                "index.html",
                error="⚠ Please enter text or upload a file."
            )

        # 🔥 Send relevant extracted content to AI
        combined_query = (
            f"Below is the uploaded document content:\n\n{extracted_text[:4000]}\n\n"
            f"User Question: {query}"
            if extracted_text else query
        )

        result = get_xai_prediction(combined_query)

        full_input_check = (extracted_text + " " + result.get("reasoning_summary", "")) if extracted_text else query

        evidence = extract_evidence(result.get("key_factors", []), full_input_check)
        fairness = check_bias(full_input_check)

        return render_template(
            "result.html",
            query=query,
            result=result,
            evidence=evidence,
            fairness=fairness,
            combined_input=combined_query   # 🔹 needed for bias simulation
        )

    return render_template("index.html")


@app.route("/feedback", methods=["POST"])
def feedback():
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_query": request.form.get("query"),
        "ai_decision": request.form.get("decision"),
        "reasoning_summary": request.form.get("reasoning"),
        "user_action": request.form.get("action", "No Action"),
        "user_feedback": request.form.get("feedback", "Not Provided"),
    }

    with open("logs/feedback_log.json", "a", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")

    return render_template(
        "success.html",
        action=entry["user_action"],
        feedback=entry["user_feedback"]
    )


# ============================================================
# 5️⃣ Fairness Simulation Route (Bias Sandbox)
# ============================================================
@app.route("/simulate_bias", methods=["POST"])
def simulate_bias():
    # Original context
    query = request.form.get("query", "")
    combined_input = request.form.get("combined_input", "")
    original_result_json = request.form.get("original_result", "{}")
    original_reasoning = request.form.get("original_reasoning", "")

    try:
        original_result = json.loads(original_result_json)
    except Exception:
        original_result = {}

    # Build modified text based on user changes to sensitive terms
    modified_text = combined_input
    fair_count = int(request.form.get("fair_count", "0") or 0)

    for i in range(fair_count):
        term = request.form.get(f"term_{i}")
        choice = request.form.get(f"replacement_choice_{i}", "")
        custom = request.form.get(f"custom_{i}", "").strip()

        if not term:
            continue

        replacement = None
        if choice == "CUSTOM" and custom:
            replacement = custom
        elif choice:
            replacement = choice
        elif custom:
            replacement = custom

        if replacement and replacement.lower() != term.lower():
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            modified_text = pattern.sub(replacement, modified_text)

    # Call model again with modified input
    sim_result = get_xai_prediction(modified_text)

    # Compute fairness + evidence for both
    original_full = combined_input + " " + original_reasoning
    modified_full = modified_text + " " + sim_result.get("reasoning_summary", "")

    original_fairness = check_bias(original_full)
    modified_fairness = check_bias(modified_full)

    original_evidence = extract_evidence(original_result.get("key_factors", []), original_full)
    modified_evidence = extract_evidence(sim_result.get("key_factors", []), modified_full)

    # Comparison summary for UI
    simulation = {
        "original_decision": original_result.get("final_decision", ""),
        "modified_decision": sim_result.get("final_decision", ""),
        "original_confidence": original_result.get("confidence_score", "Medium"),
        "modified_confidence": sim_result.get("confidence_score", "Medium"),
        "original_key_factors": original_result.get("key_factors", []),
        "modified_key_factors": sim_result.get("key_factors", []),
        "decision_changed": original_result.get("final_decision", "") != sim_result.get("final_decision", ""),
        "confidence_changed": original_result.get("confidence_score", "Medium") != sim_result.get("confidence_score", "Medium"),
    }

    return render_template(
        "result.html",
        query=query,
        result=original_result,
        evidence=original_evidence,
        fairness=original_fairness,
        combined_input=combined_input,
        simulation=simulation,
        sim_evidence=modified_evidence,
        sim_fairness=modified_fairness
    )


if __name__ == "__main__":
    app.run(debug=True)
