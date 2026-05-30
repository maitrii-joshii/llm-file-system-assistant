"""Groq-powered assistant for file-system tools."""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from . import fs_tools

try:
	from groq import Groq
except Exception:
	Groq = None

try:
	from dotenv import load_dotenv
except Exception:
	load_dotenv = None


SYSTEM_PROMPT = (
	"You are a file assistant. Use the available tools to read, search, "
	"list, and write files as needed. Ask for a missing path when required. "
	"When calling a tool, respond with only the tool call and valid JSON arguments."
)


TOOL_DEFS: List[Dict[str, Any]] = [
	{
		"type": "function",
		"function": {
			"name": "read_file",
			"description": "Read a resume file and return text + metadata.",
			"parameters": {
				"type": "object",
				"properties": {
					"filepath": {"type": "string"},
				},
				"required": ["filepath"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "list_files",
			"description": "List files in a directory with optional extension filter.",
			"parameters": {
				"type": "object",
				"properties": {
					"directory": {"type": "string"},
					"extension": {"type": "string"},
				},
				"required": ["directory"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "write_file",
			"description": "Write content to a file, creating directories if needed.",
			"parameters": {
				"type": "object",
				"properties": {
					"filepath": {"type": "string"},
					"content": {"type": "string"},
				},
				"required": ["filepath", "content"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "search_in_file",
			"description": "Search for a keyword in a file and return matches.",
			"parameters": {
				"type": "object",
				"properties": {
					"filepath": {"type": "string"},
					"keyword": {"type": "string"},
				},
				"required": ["filepath", "keyword"],
			},
		},
	},
]


def _call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
	if name == "read_file":
		return fs_tools.read_file(**args)
	if name == "list_files":
		return {"ok": True, "files": fs_tools.list_files(**args)}
	if name == "write_file":
		return fs_tools.write_file(**args)
	if name == "search_in_file":
		return fs_tools.search_in_file(**args)
	return {"ok": False, "error": f"Unknown tool: {name}"}


def _resumes_dir() -> str:
	return os.path.join(os.getcwd(), "resumes")


def _summaries_dir() -> str:
	return os.path.join(os.getcwd(), "summaries")


def _maybe_handle_direct(user_query: str) -> Optional[Dict[str, Any]]:
	query = user_query.lower()
	if "read all" in query and "resume" in query:
		files = fs_tools.list_files(_resumes_dir())
		blocks: List[str] = []
		for item in files:
			result = fs_tools.read_file(item["path"])
			if result.get("ok"):
				content = result.get("content", "")
				blocks.append(f"=== {item['name']} ===\n{content}")
			else:
				blocks.append(f"=== {item['name']} ===\nError: {result.get('error')}")
		return {"ok": True, "response": "\n\n".join(blocks)}
	if "read all" in query and "file" in query:
		path_match = re.search(
			r"([a-zA-Z]:\\[^\n\r\"']+?)(?:\s+and\b|\s+show\b|\s+with\b|$)",
			user_query,
		)
		if path_match:
			directory = path_match.group(1).rstrip(" .")
			files = fs_tools.list_files(directory)
			blocks: List[str] = []
			for item in files:
				result = fs_tools.read_file(item["path"])
				if result.get("ok"):
					content = result.get("content", "")
					blocks.append(f"=== {item['name']} ===\n{content}")
				else:
					blocks.append(f"=== {item['name']} ===\nError: {result.get('error')}")
				if len(blocks) >= 50:
					break
				return {"ok": True, "response": "\n\n".join(blocks)}
	if "find" in query and "resume" in query and "mention" in query:
		keyword_match = re.search(r"mentioning\s+(.+)", query)
		keyword = keyword_match.group(1).strip() if keyword_match else ""
		terms = [t for t in re.split(r"\s+", keyword) if t]
		files = fs_tools.list_files(_resumes_dir())
		matched: List[str] = []
		for item in files:
			read_result = fs_tools.read_file(item["path"])
			if not read_result.get("ok"):
				continue
			content = read_result.get("content", "").lower()
			if not terms:
				continue
			if all(term.lower() in content for term in terms):
				matched.append(item["name"])
		return {"ok": True, "response": "\n".join(matched) or "No matches found."}
	if "summary file" in query and "resume" in query:
		file_match = re.search(r"summary file for\s+([^\n\r]+)", user_query, re.IGNORECASE)
		filename = file_match.group(1).strip(" \"'\\.") if file_match else ""
		if filename:
			if not os.path.isabs(filename):
				filename = os.path.join(_resumes_dir(), filename)
			read_result = fs_tools.read_file(filename)
			if not read_result.get("ok"):
				return read_result
			content = read_result.get("content", "")
			lines = [line for line in content.splitlines() if line.strip()]
			summary = "\n".join(lines[:6]) if lines else "(empty file)"
			stem = os.path.splitext(os.path.basename(filename))[0]
			out_path = os.path.join(_summaries_dir(), f"{stem}_summary.txt")
			return fs_tools.write_file(out_path, summary)
	if "resumes" in query and "folder" in query:
		resumes_dir = _resumes_dir()
		if "list" in query and "file" in query:
			return _call_tool("list_files", {"directory": resumes_dir})
	path_match = re.search(
		r"([a-zA-Z]:\\[^\n\r\"']+?)(?:\s+and\b|\s+show\b|\s+with\b|$)",
		user_query,
	)
	path = path_match.group(1).rstrip(" .") if path_match else None
	if "list" in query and "file" in query and path:
		ext_match = re.search(r"\.(txt|pdf|docx)", query)
		ext = ext_match.group(0) if ext_match else None
		args = {"directory": path}
		if ext:
			args["extension"] = ext
		return _call_tool("list_files", args)
	if ("read" in query or "open" in query) and path:
		return _call_tool("read_file", {"filepath": path})
	if "search" in query and path:
		keyword_match = re.search(r"search\s+for\s+([^\n\r]+?)\s+in\s+", query)
		if keyword_match:
			keyword = keyword_match.group(1).strip(" \"'")
			return _call_tool("search_in_file", {"filepath": path, "keyword": keyword})
	if ("create" in query or "write" in query) and path:
		content_match = re.search(r"content\s*:\s*(.*)", user_query, re.IGNORECASE)
		content = content_match.group(1) if content_match else ""
		return _call_tool("write_file", {"filepath": path, "content": content})
	return None


def run_assistant(
	user_query: str,
	model: str = "llama-3.1-8b-instant",
	max_tool_calls: int = 15,
) -> Dict[str, Any]:
	"""Run the assistant with tool calling enabled."""
	if load_dotenv is not None:
		load_dotenv()
	if Groq is None:
		return {
			"ok": False,
			"error": "groq package is not installed. Run: pip install groq",
		}
	api_key = os.getenv("GROQ_API_KEY")
	if not api_key:
		return {"ok": False, "error": "GROQ_API_KEY is not set"}
	client = Groq(api_key=api_key)
	messages: List[Dict[str, Any]] = [
		{"role": "system", "content": SYSTEM_PROMPT},
		{"role": "user", "content": user_query},
	]

	try:
		tool_calls_used = 0
		while True:
			response = client.chat.completions.create(
				model=model,
				messages=messages,
				tools=TOOL_DEFS,
				tool_choice="auto",
				temperature=0,
			)
			message = response.choices[0].message
			messages.append(message)

			if not message.tool_calls:
				content = message.content or ""
				if "provide the path" in content.lower() or "provide the path to" in content.lower():
					direct_result = _maybe_handle_direct(user_query)
					if direct_result is not None:
						if not direct_result.get("ok"):
							message = direct_result.get("error") or "Unknown error"
							return {"ok": False, "error": message, "messages": []}
						if "response" in direct_result:
							return {"ok": True, "response": direct_result.get("response", ""), "messages": []}
						if "bytes_written" in direct_result:
							return {"ok": True, "response": "File written successfully.", "messages": []}
						if "files" in direct_result:
							files = direct_result.get("files", [])
							if not files:
								return {"ok": True, "response": "No files found.", "messages": []}
							lines = [
								f"{item.get('name')} ({item.get('size_bytes')} bytes)" for item in files
							]
							return {"ok": True, "response": "\n".join(lines), "messages": []}
						if "content" in direct_result:
							content = direct_result.get("content", "")
							if not content:
								return {"ok": True, "response": "(empty file)", "messages": []}
							return {"ok": True, "response": content, "messages": []}
						if "matches" in direct_result:
							matches = direct_result.get("matches", [])
							if not matches:
								return {"ok": True, "response": "No matches found.", "messages": []}
							lines = [m.get("snippet", "") for m in matches]
							return {"ok": True, "response": "\n".join(lines), "messages": []}
						return {"ok": True, "response": json.dumps(direct_result), "messages": []}
				return {
					"ok": True,
					"response": content,
					"messages": messages,
				}

			for tool_call in message.tool_calls:
				tool_calls_used += 1
				if tool_calls_used > max_tool_calls:
					return {
						"ok": False,
						"error": "Tool call limit reached",
						"messages": messages,
					}

				name = tool_call.function.name
				try:
					args = json.loads(tool_call.function.arguments or "{}")
				except json.JSONDecodeError:
					args = {}
				result = _call_tool(name, args)
				messages.append(
					{
						"role": "tool",
						"tool_call_id": tool_call.id,
						"content": json.dumps(result),
					}
				)
	except Exception:
		direct_result = _maybe_handle_direct(user_query)
		if direct_result is None:
			raise
		if not direct_result.get("ok"):
			message = direct_result.get("error") or "Unknown error"
			return {"ok": False, "error": message, "messages": []}
		if "response" in direct_result:
			return {"ok": True, "response": direct_result.get("response", ""), "messages": []}
		if "bytes_written" in direct_result:
			return {"ok": True, "response": "File written successfully.", "messages": []}
		if "files" in direct_result:
			files = direct_result.get("files", [])
			if not files:
				return {"ok": True, "response": "No files found.", "messages": []}
			lines = [
				f"{item.get('name')} ({item.get('size_bytes')} bytes)" for item in files
			]
			return {"ok": True, "response": "\n".join(lines), "messages": []}
		if "content" in direct_result:
			content = direct_result.get("content", "")
			if not content:
				return {"ok": True, "response": "(empty file)", "messages": []}
			return {"ok": True, "response": content, "messages": []}
		if "matches" in direct_result:
			matches = direct_result.get("matches", [])
			if not matches:
				return {"ok": True, "response": "No matches found.", "messages": []}
			lines = [m.get("snippet", "") for m in matches]
			return {"ok": True, "response": "\n".join(lines), "messages": []}
		return {"ok": True, "response": json.dumps(direct_result), "messages": []}


if __name__ == "__main__":
	if load_dotenv is not None:
		load_dotenv()

	query = " ".join(sys.argv[1:]).strip()
	if not query:
		print("Usage: python -m src.llm_file_assistant \"your question\"")
		raise SystemExit(1)

	result = run_assistant(query)
	if result.get("ok"):
		response = result.get("response", "")
		if os.getenv("NO_WRAP", "").strip() == "1":
			response = response.replace("\n", "\\n")
		print(response)
	else:
		print(f"Error: {result.get('error')}")
