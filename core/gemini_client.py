"""Shared Gemini API client with retry logic and file management."""

import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types as genai_types

from config.settings import GOOGLE_API_KEY, GEMINI_UPLOAD_RETRIES, GEMINI_UPLOAD_DELAY, GEMINI_FILE_TIMEOUT


class GeminiClient:
    """Wrapper around the Google Gemini API client with retry and file management."""

    def __init__(self, api_key: str = None):
        key = api_key or GOOGLE_API_KEY
        if not key:
            raise ValueError("GOOGLE_API_KEY not configured. Set it in .env or pass it directly.")
        self.client = genai.Client(api_key=key)
        self._uploaded_files = []

    def upload_file(self, filepath: Path, display_name: str = None,
                    retries: int = GEMINI_UPLOAD_RETRIES,
                    delay: int = GEMINI_UPLOAD_DELAY) -> object:
        """Upload a file to Gemini API with retries. Returns the File object or None."""
        label = display_name or filepath.name
        uploaded_file_obj = None

        for attempt in range(retries):
            try:
                uploaded_file_obj = self.client.files.upload(file=filepath)
                # Poll until ACTIVE
                timeout = GEMINI_FILE_TIMEOUT
                start = time.time()
                file_resource = self.client.files.get(name=uploaded_file_obj.name)

                while file_resource.state.name == "PROCESSING":
                    if time.time() - start > timeout:
                        raise Exception(f"Timeout waiting for {label} to become ACTIVE.")
                    time.sleep(delay)
                    file_resource = self.client.files.get(name=file_resource.name)

                if file_resource.state.name == "ACTIVE":
                    self._uploaded_files.append(file_resource)
                    return file_resource
                else:
                    raise Exception(f"File {label} not ACTIVE. Final state: {file_resource.state.name}")

            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    if uploaded_file_obj:
                        try:
                            self.client.files.delete(name=uploaded_file_obj.name)
                        except Exception:
                            pass
                    return None

    def generate_content(self, model: str, contents: list,
                         temperature: float = None,
                         log_callback=None) -> str:
        """Generate content using the Gemini API. Returns the text response."""
        config = None
        if temperature is not None:
            config = genai_types.GenerateContentConfig(
                temperature=temperature,
                candidate_count=1
            )

        kwargs = {"model": model, "contents": contents}
        if config:
            kwargs["config"] = config

        response = self.client.models.generate_content(**kwargs)

        # Check for blocking
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                reason = getattr(response.prompt_feedback.block_reason, 'name',
                                 str(response.prompt_feedback.block_reason))
                raise RuntimeError(f"Prompt blocked: {reason}")

        if not response.candidates:
            raise RuntimeError("No candidates returned from API.")

        # Extract text
        text = ""
        if hasattr(response, 'text') and response.text:
            text = response.text
        elif response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text'):
                    text += part.text

        if not text.strip():
            finish_reason = ""
            if response.candidates[0].finish_reason:
                finish_reason = response.candidates[0].finish_reason.name
            raise RuntimeError(f"Empty response from API. Finish reason: {finish_reason}")

        return text

    def cleanup_files(self):
        """Delete all uploaded files from the API."""
        for file_obj in self._uploaded_files:
            if file_obj and hasattr(file_obj, 'name'):
                try:
                    self.client.files.delete(name=file_obj.name)
                except Exception:
                    pass
        self._uploaded_files.clear()

    def cleanup_specific(self, file_objs: list):
        """Delete specific file objects from the API."""
        for file_obj in file_objs:
            if file_obj and hasattr(file_obj, 'name'):
                try:
                    self.client.files.delete(name=file_obj.name)
                except Exception:
                    pass
                if file_obj in self._uploaded_files:
                    self._uploaded_files.remove(file_obj)


def clean_html_response(text: str) -> str:
    """Remove markdown code fences from LLM-generated HTML."""
    return re.sub(r'^```html\s*|\s*```$', '', text, flags=re.MULTILINE | re.DOTALL).strip()


def safe_filename(name: str) -> str:
    """Create a filesystem-safe filename from a company name."""
    safe = re.sub(r'[^\w\s-]', '', name).strip()
    safe = re.sub(r'[-\s]+', '_', safe)
    return safe if safe else "Generated_Report"
