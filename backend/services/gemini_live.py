import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, Callable
import websockets
from core.config import settings
from core.audio import encode_audio_to_base64, decode_audio_from_base64

logger = logging.getLogger("aira.gemini_live")

# Gemini Live API WebSocket endpoint
GEMINI_LIVE_URL = (
    f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha"
    f".GenerativeService.BidiGenerateContent"
    f"?key={settings.GOOGLE_API_KEY}"
)

# AIRA system prompt - defines her persona and capabilities
AIRA_SYSTEM_PROMPT = """You are AIRA (AI Real-time Agent), an advanced multimodal AI assistant.

CRITICAL: When a user says hi or hello, respond ONLY with a simple greeting like "Hi! How can I help you today?" Nothing else.
CRITICAL: You have NO information about the user's screen. Do not mention screens, visual content, or anything visual.
CRITICAL: Screen context is ONLY available when a message starts with [SCREEN CONTEXT]. If you have not received such a message, you cannot see anything.
CRITICAL: Start every session completely fresh. Do not reference anything from previous sessions.

Your personality:
- Calm, intelligent, concise
- Never overly verbose
- Confirm before irreversible actions

Your capabilities:
- Real-time voice conversation
- Screen analysis only when user explicitly shares via [SCREEN CONTEXT] message
- Multi-step goal planning
- Web browsing and automation
- Persistent memory of user preferences"""


class GeminiLiveService:
    """
    Manages a persistent WebSocket connection to the Gemini Live API.
    Handles bidirectional audio streaming - sending user audio and
    receiving AIRA's audio responses in real time.
    """

    def __init__(self, user_name: str = "there", memory_context: str = ""):
        self.user_name = user_name
        self.memory_context = memory_context
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.session_id: Optional[str] = None
        self._receive_task: Optional[asyncio.Task] = None

    def _build_setup_message(self) -> dict:
        """
        Build the initial setup message sent to Gemini Live API.
        Uses native audio model which requires AUDIO only response modality.
        TEXT modality is not supported by gemini-2.5-flash-native-audio-latest.
        """
        system_instruction = AIRA_SYSTEM_PROMPT

        if self.memory_context:
            # Filter out any screen-related memories before injecting
            filtered_lines = [
                line for line in self.memory_context.splitlines()
                if not any(word in line.lower() for word in [
                    'screen', 'screenshot', 'sharing', 'visible', 'desktop',
                    'window', 'browser', 'tab', 'display', 'monitor'
                ])
            ]
            filtered_context = "\n".join(filtered_lines).strip()
            if filtered_context:
                system_instruction += f"\n\nWhat you know about this user:\n{filtered_context}"

        return {
            "setup": {
                "model": f"models/{settings.GEMINI_LIVE_MODEL}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": "Aoede"
                            }
                        }
                    },
                    "temperature": 0.7,
                    
                },
                "system_instruction": {
                    "parts": [{"text": system_instruction}]
                },
            }
        }

    async def connect(self) -> bool:
        """
        Establish a WebSocket connection to Gemini Live API and
        send the initial setup configuration.
        Returns True on success, False on failure.
        """
        try:
            logger.info("Connecting to Gemini Live API...")
            self.websocket = await websockets.connect(
                GEMINI_LIVE_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )

            # Send setup message
            setup_msg = self._build_setup_message()
            await self.websocket.send(json.dumps(setup_msg))

            # Wait for setup confirmation from Gemini
            response_raw = await self.websocket.recv()
            response = json.loads(response_raw)

            if "setupComplete" in response:
                self.is_connected = True
                logger.info("Gemini Live API connection established successfully.")
                return True
            else:
                logger.error(f"Unexpected setup response: {response}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Gemini Live API: {type(e).__name__}: {e}")
            self.is_connected = False
            return False

    async def send_audio_chunk(self, audio_bytes: bytes) -> None:
        """
        Stream a chunk of raw PCM audio from the user's microphone
        to the Gemini Live API for real-time processing.
        """
        if not self.is_connected or not self.websocket:
            raise RuntimeError("Not connected to Gemini Live API")

        message = {
            "realtime_input": {
                "media_chunks": [
                    {
                        "mime_type": "audio/pcm;rate=16000",
                        "data": encode_audio_to_base64(audio_bytes),
                    }
                ]
            }
        }
        await self.websocket.send(json.dumps(message))

    async def send_text(self, text: str) -> None:
        """
        Send a text message to AIRA (used for non-voice interactions
        and for injecting context like screen descriptions).
        """
        if not self.is_connected or not self.websocket:
            raise RuntimeError("Not connected to Gemini Live API")

        message = {
            "client_content": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [{"text": text}],
                    }
                ],
                "turn_complete": True,
            }
        }
        await self.websocket.send(json.dumps(message))

    async def send_screen_context(self, description: str) -> None:
        """
        Inject a screen description into AIRA's context so she
        knows what the user is currently looking at.
        """
        context_message = f"[SCREEN CONTEXT] The user's screen currently shows: {description}"
        await self.send_text(context_message)

    async def receive_responses(
        self,
        on_audio: Optional[Callable] = None,
        on_text: Optional[Callable] = None,
        on_turn_complete: Optional[Callable] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Async generator that continuously receives responses from Gemini.

        Since gemini-2.5-flash-native-audio-latest returns AUDIO only,
        we handle audio chunks and turn completion signals.
        Text transcripts come via the outputTranscript field.
        """
        if not self.is_connected or not self.websocket:
            raise RuntimeError("Not connected to Gemini Live API")

        try:
            async for raw_message in self.websocket:
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON message from Gemini")
                    continue

                # Handle server content (audio + transcript responses)
                if "serverContent" in message:
                    content = message["serverContent"]

                    # Check if this turn is complete
                    if content.get("turnComplete"):
                        response = {"type": "turn_complete"}
                        if on_turn_complete:
                            await on_turn_complete()
                        yield response
                        continue

                    # Check if user interrupted AIRA
                    if content.get("interrupted"):
                        yield {"type": "interrupted"}
                        continue

                    # Process model turn parts
                    model_turn = content.get("modelTurn", {})
                    parts = model_turn.get("parts", [])

                    for part in parts:
                        # Audio response from AIRA
                        if "inlineData" in part:
                            inline = part["inlineData"]
                            mime = inline.get("mimeType", "")
                            if "audio" in mime:
                                audio_bytes = decode_audio_from_base64(inline["data"])
                                response = {
                                    "type": "audio",
                                    "data": audio_bytes,
                                    "mime_type": mime,
                                }
                                if on_audio:
                                    await on_audio(audio_bytes)
                                yield response

                        # Text transcript from AIRA (if present)
                        if "text" in part:
                            response = {
                                "type": "text",
                                "data": part["text"],
                            }
                            if on_text:
                                await on_text(part["text"])
                            yield response

                    output_transcript = content.get("outputTranscript")
                    if output_transcript:
                        response = {
                            "type": "text",
                            "data": output_transcript,
                        }
                        if on_text:
                            await on_text(output_transcript)
                        yield response
                    # inputTranscript is independent — check outside outputTranscript block
                    input_transcript = content.get("inputTranscript")
                    if input_transcript:
                        yield {
                            "type": "user_transcript",
                            "data": input_transcript,
                        }

                # Handle tool calls (for future agent tools)
                elif "toolCall" in message:
                    yield {
                        "type": "tool_call",
                        "data": message["toolCall"],
                    }

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Gemini Live WebSocket connection closed: {e}")
            self.is_connected = False
            yield {"type": "connection_closed"}

        except Exception as e:
            logger.error(f"Error receiving from Gemini Live API: {e}")
            self.is_connected = False
            yield {"type": "error", "message": str(e)}

    async def interrupt(self) -> None:
        """
        Signal to Gemini that the user has interrupted AIRA mid-response.
        This stops the current audio generation immediately.
        """
        if not self.is_connected or not self.websocket:
            return
        message = {"client_content": {"turn_complete": False, "interrupted": True}}
        await self.websocket.send(json.dumps(message))

    async def disconnect(self) -> None:
        """Close the WebSocket connection cleanly."""
        self.is_connected = False
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("Disconnected from Gemini Live API.")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.websocket = None