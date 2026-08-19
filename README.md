# Minimal Gemini Tool Agent

A small Streamlit chat demo. Gemini chooses one of four Python tools—calculator, Open-Meteo weather, text utility, or Frankfurter currency conversion—then receives the structured tool result and writes the final reply. The UI keeps the conversation and shows each tool call, status, arguments, and result.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set `GEMINI_API_KEY` in your existing `.env` file, then start the UI:

```powershell
streamlit run app.py
```

Architecture: `app.py` manages the chat session; `agent.py` sends the prompt and tool declarations to Gemini, executes only declared Python tools, and sends their results back for a natural-language answer. No database or framework beyond Streamlit is used.

Example prompts: `What is (42 * 3) / 7?`, `What is the weather in Pune?`, `Count the words in: small tools make demos fast`, `Convert 100 USD to INR`.

Run the checks with `python -m unittest -v`.
