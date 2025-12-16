# config_groq.py
"""
This permanently configures the Groq SDK to use Llama / Mixtral models.
Import this at the top of any script that uses the Groq client.
"""

import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise SystemExit("❌ Missing GROQ_API_KEY in environment. Add your key and retry.")

# Set this so SDK and environment-based clients work automatically
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

print("✅ Groq API configured and ready for Llama models 🚀")
