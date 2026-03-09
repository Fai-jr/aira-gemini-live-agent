import base64
import logging
from typing import Optional
import google.generativeai as genai
from core.config import settings

logger = logging.getLogger("aira.gemini_vision")

genai.configure(api_key=settings.GOOGLE_API_KEY)


class GeminiVisionService:
    """
    Uses Gemini's multimodal capabilities to understand screenshots.
    AIRA calls this whenever she needs to understand what is on the user's screen.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)

    async def describe_screenshot(
        self,
        image_bytes: bytes,
        user_query: Optional[str] = None,
    ) -> str:
        """
        Send a screenshot to Gemini and get a detailed description.
        If user_query is provided, answer the specific question about the screen.
        """
        try:
            image_data = {
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }

            if user_query:
                prompt = (
                    f"The user is asking: '{user_query}'\n\n"
                    f"Look at this screenshot and answer their question. "
                    f"Be specific about what you see on screen. "
                    f"Include relevant text, buttons, form fields, URLs, or any UI elements."
                )
            else:
                prompt = (
                    "Describe what is on this screen in detail. "
                    "Include: the application or website visible, "
                    "any text content, buttons, forms, URLs, "
                    "and what actions the user could take next. "
                    "Be concise but thorough."
                )

            response = self.model.generate_content([prompt, image_data])
            description = response.text.strip()
            logger.info(f"Screenshot described: {description[:100]}...")
            return description

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return "I was unable to analyze the screen at this moment."

    async def extract_form_fields(self, image_bytes: bytes) -> dict:
        """
        Analyze a screenshot to identify form fields and their current values.
        Used by the form-fill automation feature.
        """
        try:
            image_data = {
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }

            prompt = (
                "Analyze this screenshot and identify all form fields visible. "
                "Return a JSON object with this structure: "
                '{"fields": [{"label": "field label", "type": "text|email|password|select|checkbox", '
                '"current_value": "current value or empty string", "placeholder": "placeholder text"}]}. '
                "Return only valid JSON with no explanation or markdown."
            )

            response = self.model.generate_content([prompt, image_data])
            raw = response.text.strip()

            # Clean markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            import json
            return json.loads(raw)

        except Exception as e:
            logger.error(f"Form field extraction failed: {e}")
            return {"fields": []}

    async def identify_clickable_elements(self, image_bytes: bytes) -> list:
        """
        Identify all clickable elements (buttons, links) visible on screen.
        Used by the computer-use agent for autonomous navigation.
        """
        try:
            image_data = {
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }

            prompt = (
                "List all clickable elements visible in this screenshot. "
                "Return a JSON array: "
                '[{"text": "button/link text", "type": "button|link|tab|menu", '
                '"approximate_position": "top-left|top-center|center|bottom-right etc"}]. '
                "Return only valid JSON."
            )

            response = self.model.generate_content([prompt, image_data])
            raw = response.text.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            import json
            return json.loads(raw)

        except Exception as e:
            logger.error(f"Clickable element identification failed: {e}")
            return []

    async def answer_question_about_screen(
        self,
        image_bytes: bytes,
        question: str,
    ) -> str:
        """
        Answer a specific natural language question about what is on screen.
        Example: 'What is the price of the first item?' or 'Is the form submitted?'
        """
        return await self.describe_screenshot(image_bytes, user_query=question)