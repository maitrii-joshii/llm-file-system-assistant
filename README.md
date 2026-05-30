# LLM File System Assistant

A production-style file assistant that demonstrates Groq function calling to read, search, list, and write resume files (TXT, PDF, DOCX). The project focuses on structured tool interfaces, safe file I/O, and document parsing/validation.

## Learning Objectives Mapping
- LLM tool calling: Groq tool declarations and tool responses
- Structured interfaces: JSON schema for each tool
- File I/O: safe reads, writes, and directory creation
- Parsing and validation: PDF/DOCX parsing and non-empty content checks

## Features
- Read resumes and extract text with metadata
- List files with optional extension filtering
- Search for keywords with surrounding context (case-insensitive)
- Write summary or output files
- Groq tool-calling integration with looped tool execution

## Project Structure
```
├─ src/
│  ├─ fs_tools.py
│  └─ llm_file_assistant.py
├─ video/
├─ resumes/
├─ requirements.txt
├─ .env.example
└─ README.md
```

## Setup
1. Create a virtual environment (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root (or update the existing one) with your API key:

```bash
GROQ_API_KEY=your_api_key_here
```

## Usage
Run the assistant from the project root:

```bash
python -m src.llm_file_assistant "Read all resumes in the resumes folder"
```

Example queries:
- "Read all resumes in the resumes folder"
- "Find resumes mentioning Python experience"
- "Create a summary file for resume_john_doe.pdf"

## Tool Reference
All tools return JSON-compatible dictionaries for predictable behavior in LLM tool calling.

### read_file(filepath: str) -> dict
- Reads TXT, PDF, DOCX
- Returns `content` and `metadata`
- Returns a warning and `empty=true` for empty documents

### list_files(directory: str, extension: str | None) -> list
- Lists files in a directory
- Optional extension filtering
- Returns `name`, `path`, `size_bytes`, `modified_utc`, `extension`

### write_file(filepath: str, content: str) -> dict
- Writes content to a file
- Creates directories when missing
- Returns `ok` and `bytes_written`

### search_in_file(filepath: str, keyword: str) -> dict
- Case-insensitive search
- Returns match offsets and context snippets

## Parsing and Validation Notes
- PDF support uses `PyPDF2` and raises a clear error if parsing fails.
- DOCX support uses `python-docx` and raises a clear error if parsing fails.
- If a document has no extractable text, `read_file` returns `ok=true` with a warning.

## Direct Prompt Handling
LLM tool-calling runs by default. If the model fails to produce valid tool calls, the assistant falls back to direct handling for reliability.

For Windows paths, use full paths in your prompt to avoid ambiguity.

## Output Formatting
Set `NO_WRAP=1` to print responses without line wrapping by escaping newlines.

PowerShell example:
```bash
$env:NO_WRAP=1
python -m src.llm_file_assistant "Read the file at C:\Users\MJ\Desktop\Projects\Airtribe\llm-file-system-assistant\resumes\resume_john_doe.pdf"
```

## Groq Tool Calling
The assistant defines tool schemas and uses Groq tool calls to select and run tools. Tool responses are sent back to the model until it returns a final natural-language answer.

Default model is `llama-3.1-8b-instant`. You can override it by passing a different `model` to `run_assistant()`.

## Sample Data
Dummy resumes are available in the `resumes/` folder (9 files). PDF samples are generated with `reportlab`.

## Troubleshooting
- Missing API key: set `GROQ_API_KEY` in `.env`.
- PDF/DOCX errors: install optional dependencies from `requirements.txt`.
- Empty content: the document likely has no extractable text.

## Demo Video File
Demo recording is available at `video/llm-file-system-assistant-demo.webm`.
