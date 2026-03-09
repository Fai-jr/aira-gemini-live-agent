import json
import logging
from typing import Optional
import google.generativeai as genai
from core.config import settings

logger = logging.getLogger("aira.goal_planner")
genai.configure(api_key=settings.GOOGLE_API_KEY)


class GoalPlanner:
    """
    Breaks down high-level user intent into concrete executable steps.
    Uses Gemini AI to detect intent — no hardcoded keywords.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)

    async def is_multi_step_intent(self, user_utterance: str) -> bool:
        """
        Use Gemini to determine if the utterance needs browser/computer action.
        No hardcoded keywords — understands natural language intent.
        """
        # Fast pre-filter: very short or purely conversational utterances
        lower = user_utterance.lower().strip()
        if len(lower) < 5:
            return False

        # Pure conversation — skip AI call entirely for speed
        pure_conversation = [
            "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
            "bye", "goodbye", "yes", "no", "sure", "cool", "great",
            "nice", "good", "wow", "really", "interesting",
        ]
        if lower in pure_conversation:
            return False

        try:
            prompt = (
                "You are classifying whether a user request requires a computer action "
                "(like opening a browser, searching the web, navigating to a website, "
                "filling a form, playing a video, booking something, downloading something, "
                "or any multi-step task on a computer).\n\n"
                f'User said: "{user_utterance}"\n\n'
                "Reply with only a single word: YES or NO.\n"
                "YES = requires opening browser or doing something on the computer.\n"
                "NO = just a question, conversation, or something AIRA can answer by talking.\n"
                "Examples:\n"
                '"search for flights to Lagos" → YES\n'
                '"open youtube and play music" → YES\n'
                '"find me the latest news" → YES\n'
                '"what is the capital of France" → NO\n'
                '"how are you" → NO\n'
                '"tell me a joke" → NO\n'
                '"book me a hotel in Douala" → YES\n'
                '"what time is it" → NO\n'
                '"look up hackathons happening this month" → YES\n'
            )

            response = self.model.generate_content(prompt)
            answer = response.text.strip().upper()
            result = answer.startswith("YES")
            logger.info(f"Intent detection: '{user_utterance[:50]}' → {answer} → multi_step={result}")
            return result

        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            # Fallback: if AI fails, assume it needs planning to be safe
            return True

    async def plan(
        self,
        user_goal: str,
        screen_context: Optional[str] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        """
        Generate a multi-step plan for achieving the user's goal.
        Returns a structured plan dict.
        """
        context_parts = []
        if screen_context:
            context_parts.append(f"Current screen: {screen_context}")
        if memory_context:
            context_parts.append(f"What I know about this user:\n{memory_context}")
        context_string = "\n\n".join(context_parts)

        prompt = (
            "You are AIRA's goal planning engine. "
            "Break down the following user goal into a sequence of concrete steps "
            "that can be executed in a web browser.\n\n"
            f"User goal: {user_goal}\n\n"
            f"{context_string}\n\n"
            "Return a JSON object with this exact structure:\n"
            "{\n"
            '  "goal_summary": "one sentence description of the goal",\n'
            '  "requires_confirmation": true or false,\n'
            '  "steps": [\n'
            "    {\n"
            '      "step": 1,\n'
            '      "action": "description of what to do",\n'
            '      "type": "browser|search|form_fill|vision|confirm|general",\n'
            '      "details": "specific parameters or data needed"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Mark requires_confirmation as true only if the action involves sending emails, "
            "making purchases, deleting data, or other irreversible actions.\n"
            "- Keep steps atomic - one action per step.\n"
            "- For search tasks, use type 'search' and put the search query in details.\n"
            "- For navigation, use type 'browser' and put the URL in details.\n"
            "- Return only valid JSON, no extra text."
        )

        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            plan = json.loads(raw)
            logger.info(
                f"Plan generated for goal '{user_goal[:50]}': "
                f"{len(plan.get('steps', []))} steps"
            )
            return plan

        except Exception as e:
            logger.error(f"Goal planning failed: {e}")
            return {
                "goal_summary": user_goal,
                "requires_confirmation": False,
                "steps": [
                    {
                        "step": 1,
                        "action": f"Search for: {user_goal}",
                        "type": "search",
                        "details": user_goal,
                    }
                ],
            }