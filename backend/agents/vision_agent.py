import base64
import logging
from typing import Optional
import google.generativeai as genai
from core.config import settings

logger = logging.getLogger("aira.vision_agent")

genai.configure(api_key=settings.GOOGLE_API_KEY)


class VisionAgent:
    """
    AIRA's eyes. Analyzes screenshots using Gemini's multimodal
    capabilities to understand what is on the user's screen.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)

    def _image_part(self, image_bytes: bytes) -> dict:
        return {
            "mime_type": "image/png",
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        }

    async def describe_screen(
        self,
        image_bytes: bytes,
        user_query: Optional[str] = None,
    ) -> str:
        """
        Give a full description of what is on screen.
        If user_query is provided, answer that specific question.
        """
        try:
            if user_query:
                prompt = (
                    f"The user is asking: '{user_query}'\n\n"
                    f"Look at this screenshot and answer their question directly. "
                    f"Be specific about what you see — include text, buttons, "
                    f"URLs, form fields, and any relevant UI elements."
                )
            else:
                prompt = (
                    "Describe what is visible on this screen in detail. "
                    "Include: the application or website, any visible text, "
                    "buttons, forms, URLs, images, and what actions "
                    "the user could take next. Be concise but complete."
                )

            response = self.model.generate_content([
                prompt,
                self._image_part(image_bytes),
            ])
            description = response.text.strip()
            logger.info(f"Screen described successfully: {description[:80]}...")
            return description

        except Exception as e:
            logger.error(f"Screen description failed: {e}")
            return "I was unable to analyze the screen at this moment."

    async def extract_text_from_screen(self, image_bytes: bytes) -> str:
        """
        Extract all readable text from a screenshot.
        Useful for reading articles, documents, or any on-screen text.
        """
        try:
            prompt = (
                "Extract all readable text from this screenshot. "
                "Preserve the structure and layout as much as possible. "
                "Include headings, paragraphs, labels, buttons, and any "
                "other visible text. Return only the extracted text."
            )
            response = self.model.generate_content([
                prompt,
                self._image_part(image_bytes),
            ])
            return response.text.strip()

        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""

    async def identify_current_app(self, image_bytes: bytes) -> dict:
        """
        Identify what application or website is currently open.
        Returns a structured dict with app info.
        """
        import json
        try:
            prompt = (
                "Look at this screenshot and identify the application or website. "
                "Return a JSON object with this structure: "
                '{"app_name": "name", "app_type": "browser|desktop|mobile", '
                '"current_url": "url if browser else null", '
                '"page_title": "title of the page or window", '
                '"primary_action": "what the user is most likely doing"}. '
                "Return only valid JSON."
            )
            response = self.model.generate_content([
                prompt,
                self._image_part(image_bytes),
            ])
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            return json.loads(raw)

        except Exception as e:
            logger.error(f"App identification failed: {e}")
            return {
                "app_name": "Unknown",
                "app_type": "unknown",
                "current_url": None,
                "page_title": "Unknown",
                "primary_action": "Unknown",
            }

    async def extract_form_fields(self, image_bytes: bytes) -> dict:
        """
        Identify all form fields visible on screen.
        Used by the form-fill automation feature.
        """
        import json
        try:
            prompt = (
                "Analyze this screenshot and identify all form fields. "
                "Return a JSON object: "
                '{"fields": [{"label": "field label", '
                '"type": "text|email|password|select|checkbox|radio|textarea", '
                '"current_value": "current value or empty string", '
                '"placeholder": "placeholder text or empty string", '
                '"required": true or false}]}. '
                "Return only valid JSON."
            )
            response = self.model.generate_content([
                prompt,
                self._image_part(image_bytes),
            ])
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            return json.loads(raw)

        except Exception as e:
            logger.error(f"Form field extraction failed: {e}")
            return {"fields": []}

    async def find_element(
        self,
        image_bytes: bytes,
        element_description: str,
    ) -> dict:
        """
        Find a specific UI element on screen by description.
        Returns position information for the computer-use agent.
        """
        import json
        try:
            prompt = (
                f"Find the element matching this description: '{element_description}'\n\n"
                "Look at the screenshot and locate this element. "
                "Return a JSON object: "
                '{"found": true or false, '
                '"element_text": "exact text of the element", '
                '"element_type": "button|link|input|image|text", '
                '"location": "describe where it is on screen", '
                '"confidence": 0.0 to 1.0}. '
                "Return only valid JSON."
            )
            response = self.model.generate_content([
                prompt,
                self._image_part(image_bytes),
            ])
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            return json.loads(raw)

        except Exception as e:
            logger.error(f"Element finding failed: {e}")
            return {"found": False, "confidence": 0.0}

    async def suggest_next_actions(self, image_bytes: bytes) -> list:
        """
        Look at the screen and suggest what AIRA could do next.
        Used for proactive suggestions to the user.
        """
        import json
        try:
            prompt = (
                "Look at this screenshot and suggest 3 helpful actions "
                "AIRA could take to assist the user. "
                "Return a JSON array: "
                '[{"action": "short action description", '
                '"reason": "why this would be helpful", '
                '"type": "browser|search|form_fill|read|navigate"}]. '
                "Return only valid JSON."
            )
            response = self.model.generate_content([
                prompt,
                self._image_part(image_bytes),
            ])
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            return json.loads(raw)

        except Exception as e:
            logger.error(f"Action suggestion failed: {e}")
            return []