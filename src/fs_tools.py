import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _iso_mtime(path: str) -> str:
	return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()


def _file_metadata(path: str) -> Dict[str, object]:
	return {
		"name": os.path.basename(path),
		"path": path,
		"size_bytes": os.path.getsize(path),
		"modified_utc": _iso_mtime(path),
		"extension": os.path.splitext(path)[1].lower(),
	}


def _read_txt(path: str) -> str:
	try:
		with open(path, "r", encoding="utf-8") as f:
			return f.read()
	except UnicodeDecodeError:
		with open(path, "r", encoding="latin-1") as f:
			return f.read()


def _read_pdf(path: str) -> str:
	try:
		from PyPDF2 import PdfReader
	except Exception as exc:  # pragma: no cover - optional dependency
		raise RuntimeError("PyPDF2 is required to read PDF files") from exc
	try:
		reader = PdfReader(path)
		parts: List[str] = []
		for page in reader.pages:
			parts.append(page.extract_text() or "")
		return "\n".join(parts).strip()
	except Exception as exc:
		raise RuntimeError("Failed to parse PDF content") from exc


def _read_docx(path: str) -> str:
	try:
		from docx import Document
	except Exception as exc:  # pragma: no cover - optional dependency
		raise RuntimeError("python-docx is required to read DOCX files") from exc
	try:
		doc = Document(path)
		return "\n".join(p.text for p in doc.paragraphs).strip()
	except Exception as exc:
		raise RuntimeError("Failed to parse DOCX content") from exc


def read_file(filepath: str) -> Dict[str, object]:
	"""
	Read a file (PDF, TXT, DOCX) and return content + metadata.
	"""
	try:
		if not os.path.exists(filepath):
			return {"ok": False, "error": "File not found", "filepath": filepath}
		if not os.path.isfile(filepath):
			return {"ok": False, "error": "Path is not a file", "filepath": filepath}

		ext = os.path.splitext(filepath)[1].lower()
		if ext in {".txt", ""}:
			content = _read_txt(filepath)
		elif ext == ".pdf":
			content = _read_pdf(filepath)
		elif ext == ".docx":
			content = _read_docx(filepath)
		else:
			return {
				"ok": False,
				"error": f"Unsupported file extension: {ext or '(none)'}",
				"filepath": filepath,
			}

		metadata = _file_metadata(filepath)
		result: Dict[str, object] = {
			"ok": True,
			"filepath": filepath,
			"metadata": metadata,
			"content": content,
		}
		if not content.strip():
			result["warning"] = "No text extracted from document"
			result["empty"] = True
		return result
	except Exception as exc:
		return {
			"ok": False,
			"error": str(exc),
			"filepath": filepath,
		}


def list_files(directory: str, extension: Optional[str] = None) -> List[Dict[str, object]]:
	"""
	List files in a directory with optional extension filter.
	"""
	results: List[Dict[str, object]] = []
	if extension:
		ext = extension.lower()
		if not ext.startswith("."):
			ext = "." + ext
	else:
		ext = None

	try:
		if not os.path.exists(directory):
			os.makedirs(directory, exist_ok=True)
		for entry in os.scandir(directory):
			if not entry.is_file():
				continue
			if ext and not entry.name.lower().endswith(ext):
				continue
			results.append(_file_metadata(entry.path))
	except FileNotFoundError:
		return []

	return results


def write_file(filepath: str, content: str) -> Dict[str, object]:
	"""
	Write content to a file, creating directories if needed.
	"""
	try:
		if os.path.exists(filepath):
			if os.path.isdir(filepath):
				return {"ok": False, "error": "Path is a directory", "filepath": filepath}
			os.remove(filepath)
		os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
		with open(filepath, "w", encoding="utf-8") as f:
			f.write(content)
		return {
			"ok": True,
			"filepath": filepath,
			"bytes_written": len(content.encode("utf-8")),
		}
	except Exception as exc:
		return {"ok": False, "error": str(exc), "filepath": filepath}


def search_in_file(filepath: str, keyword: str) -> Dict[str, object]:
	"""
	Case-insensitive keyword search with surrounding context.
	"""
	if not keyword:
		return {"ok": False, "error": "Keyword is required", "filepath": filepath}

	read_result = read_file(filepath)
	if not read_result.get("ok"):
		return read_result

	content = read_result.get("content", "")
	haystack = content.lower()
	needle = keyword.lower()

	matches: List[Dict[str, object]] = []
	start = 0
	context = 40
	while True:
		idx = haystack.find(needle, start)
		if idx == -1:
			break
		end = idx + len(needle)
		snippet_start = max(0, idx - context)
		snippet_end = min(len(content), end + context)
		snippet = content[snippet_start:snippet_end]
		matches.append(
			{
				"start": idx,
				"end": end,
				"snippet": snippet,
			}
		)
		start = end

	return {
		"ok": True,
		"filepath": filepath,
		"keyword": keyword,
		"match_count": len(matches),
		"matches": matches,
		"metadata": read_result.get("metadata"),
	}


__all__ = [
	"read_file",
	"list_files",
	"write_file",
	"search_in_file",
]
