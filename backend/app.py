import os
import json
import time
import io
from flask import Flask, request, Response, jsonify, stream_with_context, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER

load_dotenv()

app = Flask(__name__)
CORS(app)

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai')
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-5.1')

openai_client = None

def get_openai_client():
    global openai_client
    if openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key or 'blahblah' in api_key:
            raise ValueError("OpenAI API key not configured properly. Please add your real key to backend/.env")
        openai_client = OpenAI(api_key=api_key)
    return openai_client

SYSTEM_PROMPT = """You are a legal document assistant. You MUST use function calls to create documents.

CRITICAL RULES:
1. NEVER output document content as regular text. Documents ONLY appear through the generate_document function.
2. NEVER make up or assume information the user hasn't provided, UNLESS they explicitly say "make up the details" or similar.
3. ALWAYS call extract_information EVERY TIME the user provides new information.
4. ALWAYS ask for missing required information before generating a document.

EXAMPLE REQUIRED INFORMATION BY DOCUMENT TYPE:
- NDA: party1_name, party2_name, governing_law, term_length, nda_type (mutual/one-way)
- Employment Agreement: employer_name, employee_name, position, salary, start_date
- Service Agreement: provider_name, client_name, services_description, payment_terms, timeline
Based on the type of document, determine the required information.

WORKFLOW:
1. When user requests a document, call extract_information to track what data you have
2. Ask for missing required info naturally
3. EVERY TIME user provides info, call extract_information to update tracked data
4. When all info is collected (or user says "make it up"), call generate_document with:
   - document_type
   - document_content: The COMPLETE filled-in document (no placeholders!)

CRITICAL: When calling generate_document, the document_content must have ALL values filled in.
Example: "This Agreement is between **Company ABC** and **Company XYZ**..."
NOT: "This Agreement is between **{{party1_name}}** and **{{party2_name}}**..."

INTERNAL KEY NAMES (use in function arguments and templates ONLY - never show to user):
- NDA: party1_name, party2_name, governing_law, term_length, nda_type
- Employment: employer_name, employee_name, position, salary, start_date
- Service: provider_name, client_name, services, payment_terms, timeline

IMPORTANT: When TALKING to the user, ask naturally like a human:
- GOOD: "What are the names of the two companies?"
- BAD: "Please provide party1_name and party2_name"

TEMPLATE FORMAT (for extract_information):
- Use {{key_name}} matching the internal keys above
- Example: "Between **{{party1_name}}** and **{{party2_name}}**, governed by {{governing_law}}..."
- Use markdown: # for title, ## for sections, **bold**, - for bullets
- Keep SHORT (3-5 sections, 2-5 points each)

EDITING:
When the user asks to edit, the CURRENT DOCUMENT is already provided in your context above.
Use the apply_edits function with the full updated document. Do NOT ask the user to paste the document.
Copy the entire document exactly, changing ONLY what was requested.

RESPONSE FLOW:
- extract_information: NO intro text. Just call the function, then ask for missing info naturally.
- generate_document: Say "I'll create the document now." BEFORE calling. Provide summary AFTER.
- apply_edits: Say "I'll update the document now." BEFORE calling. Confirm edit AFTER.

Speak naturally. Never mention functions or technical details to the user."""

FUNCTION_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "extract_information",
            "description": "Store information and template for document generation. Call on FIRST request to create template, then on each new piece of info to update data. Does NOT generate the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "description": "Type of document (NDA, Employment Agreement, Service Agreement, etc.)"
                    },
                    "extracted_data": {
                        "type": "object",
                        "description": "Key-value pairs of information. Keys should match {{placeholder}} names in template.",
                        "additionalProperties": True
                    },
                    "missing_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of required field names still needed"
                    },
                    "template": {
                        "type": "string",
                        "description": "Document template with {{placeholder}} syntax. Only provide on FIRST call for a new document type. Use field names like {{party1_name}}, {{term_length}}, etc."
                    }
                },
                "required": ["document_type", "extracted_data", "missing_fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_document",
            "description": "Generate the document using the collected data. Fill in ALL placeholders with the values from extracted_data before calling this. The document_content should have no {{placeholders}} remaining.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "description": "Type of document"
                    },
                    "document_content": {
                        "type": "string",
                        "description": "The COMPLETE document in markdown with ALL values filled in. NO {{placeholders}} should remain."
                    }
                },
                "required": ["document_type", "document_content"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "apply_edits",
            "description": "Edit an existing document. Copy the entire current document exactly, changing ONLY the specific part requested.",
            "parameters": {
                "type": "object",
                "properties": {
                    "edit_description": {
                        "type": "string",
                        "description": "Brief description of the change made"
                    },
                    "updated_document": {
                        "type": "string",
                        "description": "The COMPLETE document with ONLY the requested change applied"
                    }
                },
                "required": ["edit_description", "updated_document"]
            }
        }
    }
]

conversations = {}
documents = {}
pdf_cache = {}
extracted_info = {}

def strip_markdown_fences(content):
    if not content:
        return content
    content = content.strip()
    if content.startswith('```markdown'):
        content = content[11:]
    elif content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]
    return content.strip()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "provider": LLM_PROVIDER, "model": MODEL_NAME})

def build_messages(session_id):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if session_id in extracted_info:
        info = extracted_info[session_id]
        extracted_context = f"\n\nCURRENT SESSION DATA:\n"
        extracted_context += f"Document Type: {info.get('document_type', 'Not specified')}\n"
        extracted_context += f"Collected Data: {json.dumps(info.get('extracted_data', {}))}\n"
        missing = info.get('missing_fields', [])
        if missing:
            extracted_context += f"Still Missing: {', '.join(missing)}\n"
        else:
            extracted_context += "Status: All required info collected - ready to generate\n"
        if info.get('template'):
            extracted_context += f"Template: Already stored (do not resend)\n"
        messages[0]['content'] += extracted_context
    
    if session_id in documents:
        doc_content = documents[session_id].get('content', '')
        if doc_content:
            doc_context = f"""

=== CURRENT DOCUMENT (YOU HAVE THIS - DO NOT ASK USER FOR IT) ===
{doc_content}
=== END CURRENT DOCUMENT ===

For edits: Use apply_edits with the FULL document above, changing ONLY what was requested. Do NOT ask the user to provide the document."""
            messages[0]['content'] += doc_context
    
    messages.extend(conversations[session_id])
    return messages

def get_completion_params(messages):
    params = {
        "model": MODEL_NAME,
        "messages": messages,
        "tools": FUNCTION_DEFINITIONS,
        "tool_choice": "auto",
        "stream": True,
        "temperature": 0.7
    }
    if "gpt-5" in MODEL_NAME.lower():
        params["max_completion_tokens"] = 4000
    else:
        params["max_tokens"] = 4000
    return params

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    if session_id not in conversations:
        conversations[session_id] = []
    
    conversations[session_id].append({"role": "user", "content": message})
    
    def generate():
        try:
            messages = build_messages(session_id)
            
            while True:
                stream = get_openai_client().chat.completions.create(**get_completion_params(messages))
                
                tool_calls_data = {}
                tool_call_ids = {}
                full_response = ""
                
                for chunk in stream:
                    choice = chunk.choices[0] if chunk.choices else None
                    if not choice:
                        continue
                    
                    if choice.delta.tool_calls:
                        for tool_call in choice.delta.tool_calls:
                            idx = tool_call.index
                            if idx not in tool_calls_data:
                                tool_calls_data[idx] = {'name': None, 'args': ''}
                                tool_call_ids[idx] = None
                            
                            if tool_call.id:
                                tool_call_ids[idx] = tool_call.id
                            if tool_call.function.name:
                                tool_calls_data[idx]['name'] = tool_call.function.name
                            if tool_call.function.arguments:
                                tool_calls_data[idx]['args'] += tool_call.function.arguments
                    
                    elif choice.delta.content:
                        content = choice.delta.content
                        full_response += content
                        yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                        time.sleep(0.01)
                
                if not tool_calls_data:
                    if full_response:
                        conversations[session_id].append({"role": "assistant", "content": full_response})
                    break
                
                if full_response:
                    yield f"data: {json.dumps({'type': 'new_message'})}\n\n"
                
                assistant_message = {"role": "assistant", "content": full_response if full_response else None, "tool_calls": []}
                tool_results = []
                
                for idx in sorted(tool_calls_data.keys()):
                    function_name = tool_calls_data[idx]['name']
                    function_args = tool_calls_data[idx]['args']
                    tool_call_id = tool_call_ids.get(idx, f"call_{idx}")
                    
                    if not function_name:
                        continue
                    
                    yield f"data: {json.dumps({'type': 'function_call', 'function': function_name})}\n\n"
                    
                    assistant_message["tool_calls"].append({
                        "id": tool_call_id,
                        "type": "function",
                        "function": {"name": function_name, "arguments": function_args}
                    })
                    
                    try:
                        arguments = json.loads(function_args) if function_args else {}
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    result = ""
                    
                    if function_name == "extract_information":
                        doc_type = arguments.get('document_type', '')
                        extracted_data = arguments.get('extracted_data', {})
                        missing_fields = arguments.get('missing_fields', [])
                        template = arguments.get('template', '')
                        
                        
                        if session_id not in extracted_info:
                            extracted_info[session_id] = {'document_type': doc_type, 'extracted_data': {}, 'missing_fields': [], 'template': ''}
                        
                        extracted_info[session_id]['document_type'] = doc_type
                        extracted_info[session_id]['extracted_data'].update(extracted_data)
                        extracted_info[session_id]['missing_fields'] = missing_fields
                        if template:
                            extracted_info[session_id]['template'] = strip_markdown_fences(template)
                        
                        
                        if missing_fields:
                            result = f"Stored data. Missing required fields: {missing_fields}. Ask the user for this information naturally."
                        else:
                            result = "All required information collected. You may now call generate_document to create the document."
                    
                    elif function_name == "generate_document":
                        doc_type = arguments.get('document_type', '')
                        doc_content = strip_markdown_fences(arguments.get('document_content', ''))
                        
                        if not doc_content:
                            result = "Error: No document content provided."
                        else:
                            metadata = {}
                            if session_id in extracted_info:
                                metadata = extracted_info[session_id].get('extracted_data', {})
                            
                            yield f"data: {json.dumps({'type': 'document_start'})}\n\n"
                            
                            lines = doc_content.split('\n')
                            streamed_content = ''
                            for line in lines:
                                streamed_content += line + '\n'
                                yield f"data: {json.dumps({'type': 'document_chunk', 'content': streamed_content})}\n\n"
                                time.sleep(0.03)
                            
                            doc_content = doc_content.strip()
                            
                            documents[session_id] = {
                                'type': doc_type,
                                'content': doc_content,
                                'metadata': metadata,
                                'created_at': datetime.now().isoformat()
                            }
                            
                            if session_id in pdf_cache:
                                del pdf_cache[session_id]
                            
                            yield f"data: {json.dumps({'type': 'document_complete', 'document': doc_content})}\n\n"
                            result = "Document generated successfully and shown to user."
                    
                    elif function_name == "apply_edits":
                        updated_doc = strip_markdown_fences(arguments.get('updated_document', ''))
                        edit_desc = arguments.get('edit_description', 'changes')
                        
                        if updated_doc and session_id in documents:
                            documents[session_id]['content'] = updated_doc
                            documents[session_id]['last_edited'] = datetime.now().isoformat()
                            
                            if session_id in pdf_cache:
                                del pdf_cache[session_id]
                            
                            yield f"data: {json.dumps({'type': 'document_generated', 'document': updated_doc})}\n\n"
                            result = f"Document updated: {edit_desc}"
                        else:
                            result = "Error: Could not update document"
                    
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result
                    })
                
                yield f"data: {json.dumps({'type': 'new_message'})}\n\n"
                
                messages.append(assistant_message)
                messages.extend(tool_results)
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )

@app.route('/reset', methods=['POST'])
def reset_conversation():
    data = request.json
    session_id = data.get('session_id', 'default')

    if session_id in conversations:
        del conversations[session_id]
    if session_id in documents:
        del documents[session_id]
    if session_id in pdf_cache:
        del pdf_cache[session_id]
    if session_id in extracted_info:
        del extracted_info[session_id]
    
    return jsonify({"status": "reset", "session_id": session_id})

@app.route('/document/<session_id>', methods=['GET'])
def get_document(session_id):
    if session_id in documents:
        return jsonify({
            "status": "success",
            "document": documents[session_id]
        })
    return jsonify({"status": "not_found", "message": "No document found"})

@app.route('/document/<session_id>/pdf', methods=['GET'])
def get_document_pdf(session_id):
    try:
        
        if session_id not in documents:
            return jsonify({"status": "not_found"}), 404
        
        if session_id not in pdf_cache:
            doc_content = documents[session_id].get('content', '')
            if not doc_content:
                return jsonify({"status": "error"}), 500
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter,
                                   rightMargin=72, leftMargin=72,
                                   topMargin=72, bottomMargin=36)
            
            styles = getSampleStyleSheet()
            story = []
            
            import re
            
            def process_markdown_to_html(text):
                text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
                text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
                text = text.replace('&', '&amp;')
                text = text.replace('<', '&lt;').replace('>', '&gt;')
                text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
                text = text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
                return text
            
            lines = doc_content.split('\n')
            for line in lines:
                original_line = line
                line = line.strip()
                
                if not line:
                    story.append(Spacer(1, 0.2*inch))
                elif line.startswith('# '):
                    title_text = process_markdown_to_html(line[2:])
                    story.append(Paragraph(title_text, styles['Title']))
                    story.append(Spacer(1, 0.3*inch))
                elif line.startswith('## '):
                    heading_text = process_markdown_to_html(line[3:])
                    story.append(Paragraph(heading_text, styles['Heading1']))
                    story.append(Spacer(1, 0.2*inch))
                elif line.startswith('### '):
                    heading_text = process_markdown_to_html(line[4:])
                    story.append(Paragraph(heading_text, styles['Heading2']))
                    story.append(Spacer(1, 0.15*inch))
                elif line.startswith(('- ', '* ', '• ')):
                    bullet_text = line[2:] if len(line) > 2 else ''
                    bullet_text = process_markdown_to_html(bullet_text)
                    bullet_style = ParagraphStyle('Bullet', parent=styles['Normal'], 
                                                leftIndent=36, bulletIndent=18)
                    story.append(Paragraph(bullet_text, bullet_style, bulletText='•'))
                elif line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                    number_match = re.match(r'^(\d+)\.\s*(.*)', line)
                    if number_match:
                        number, text = number_match.groups()
                        text = process_markdown_to_html(text)
                        list_style = ParagraphStyle('NumberedList', parent=styles['Normal'],
                                                  leftIndent=36, bulletIndent=18)
                        story.append(Paragraph(text, list_style, bulletText=f'{number}.'))
                else:
                    if line:
                        formatted_text = process_markdown_to_html(line)
                        story.append(Paragraph(formatted_text, styles['Normal']))
            
            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            pdf_cache[session_id] = pdf_data
        
        return send_file(
            io.BytesIO(pdf_cache[session_id]),
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'document_{session_id}.pdf'
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    import sys
    port = 5001
    if len(sys.argv) > 1 and '--port=' in sys.argv[1]:
        port = int(sys.argv[1].split('=')[1])
    app.run(debug=True, port=port, threaded=True)
