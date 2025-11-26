# Lexiden - Legal Document Assistant

AI-powered legal document generation with real-time streaming and intelligent conversation.

## Key Features

- **Real-time SSE Streaming** - Token-by-token document generation with live preview
- **3 LLM Functions** - `extract_information`, `generate_document`, `apply_edits`
- **Smart Prompting** - Conversational data collection before document creation
- **PDF Export** - Markdown-to-PDF conversion with proper formatting
- **Edit Support** - Modify generated documents through natural language

## Challenge Requirements

| Requirement | Implementation |
|-------------|----------------|
| SSE Streaming (30%) | Real-time streaming to chat and document preview |
| LLM Function Calling (40%) | 3 functions: extract_information, generate_document, apply_edits |
| System Prompts (30%) | Structured prompts for data collection and document generation |

## Quick Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with your API key
echo "OPENAI_API_KEY=your_key_here" > .env
echo "MODEL_NAME=gpt-4o" >> .env

python app.py             # Runs on http://localhost:5001
```

### Frontend
```bash
cd frontend
npm install
npm start                 # Runs on http://localhost:3000
```

## Environment Variables

```env
OPENAI_API_KEY=your_key_here
MODEL_NAME=gpt-5.1
```

## How It Works

1. **User requests document** → LLM calls `extract_information`
2. **LLM asks for missing details** → User provides info
3. **All data collected** → LLM calls `generate_document`
4. **Document streams** → Live preview with PDF export
5. **User requests changes** → LLM calls `apply_edits`

## Supported Documents

- Non-Disclosure Agreements (NDA)
- Employment Agreements
- Service Agreements
- Any custom legal document!!

## Tech Stack

- **Backend**: Flask, OpenAI API, ReportLab (PDF)
- **Frontend**: React, Server-Sent Events
- **Streaming**: SSE for real-time updates

---

*Built for Lexiden AI Tech Challenge*
