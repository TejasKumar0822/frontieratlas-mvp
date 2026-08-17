from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any

import httpx
from google import genai

from src.utils.text import semantic_chunks


SYSTEM = """You are a deterministic information extraction engine.

Extract ONLY facts explicitly supported by the supplied source text.

Never invent values.

If a value is not present in the source text, return null.

Return JSON only.

The output must match the requested schema exactly.

Preserve source URLs as supplied by the source data.

Do not infer facts that are not explicitly supported.
"""


class LLMOrchestrator:
    """
    Multi-provider LLM extraction engine.

    Provider priority:

        1. Gemini
        2. Groq
        3. DeepSeek

    If one provider fails because of quota, rate limits,
    unavailable models, authentication problems, or another
    provider-side error, the next provider is attempted.

    The application always enforces the requested recordType.
    """

    def __init__(self):

        self.providers = [
            (
                "gemini",
                os.getenv("GEMINI_API_KEY"),
                os.getenv(
                    "GEMINI_MODEL",
                    "gemini-3.5-flash",
                ),
            ),
            (
                "groq",
                os.getenv("GROQ_API_KEY"),
                os.getenv(
                    "GROQ_MODEL",
                    "llama-3.3-70b-versatile",
                ),
            ),
            (
                "deepseek",
                os.getenv("DEEPSEEK_API_KEY"),
                os.getenv(
                    "DEEPSEEK_MODEL",
                    "deepseek-chat",
                ),
            ),
        ]

    # =========================================================
    # PUBLIC EXTRACTION METHOD
    # =========================================================

    async def extract(
        self,
        text: str,
        schema: dict,
    ):
        """
        Extract structured information from source text.

        Provider fallback:

            Gemini → Groq → DeepSeek

        A 429/quota error causes immediate fallback instead
        of repeatedly retrying the exhausted provider.
        """

        chunks = semantic_chunks(
            text,
            max_chars=10000,
        )

        if not chunks:
            chunks = [text]

        errors = []

        for provider, key, model in self.providers:

            if not key:
                continue

            print(
                f"LLM provider: {provider} "
                f"({model})"
            )

            try:

                result = await self._provider_with_retries(
                    provider=provider,
                    key=key,
                    model=model,
                    chunks=chunks,
                    schema=schema,
                )

                # -------------------------------------------------
                # The application knows the record type.
                # Never allow the LLM to change it.
                # -------------------------------------------------

                if isinstance(result, dict):

                    expected_type = schema.get(
                        "recordType"
                    )

                    if expected_type:
                        result["recordType"] = (
                            expected_type
                        )

                print(
                    f"LLM success: {provider}"
                )

                return result

            except Exception as e:

                error_message = str(e)

                errors.append(
                    f"{provider}: {error_message}"
                )

                print(
                    f"LLM provider failed: "
                    f"{provider} -> "
                    f"{error_message}"
                )

                # Immediately move to the next provider.
                continue

        if not errors:

            raise RuntimeError(
                "No LLM providers are configured. "
                "Set at least one of GEMINI_API_KEY, "
                "GROQ_API_KEY, or DEEPSEEK_API_KEY."
            )

        raise RuntimeError(
            "All LLM providers failed: "
            + " | ".join(errors)
        )

    # =========================================================
    # PROVIDER RETRY LOGIC
    # =========================================================

    async def _provider_with_retries(
        self,
        provider: str,
        key: str,
        model: str,
        chunks: list[str],
        schema: dict,
    ):
        """
        Handle retries for a single provider.

        Important behavior:

        429:
            Immediately fail this provider and move to the
            next provider.

        413:
            Reduce payload size and retry.

        5xx:
            Retry with exponential backoff.

        Timeout/network:
            Retry with exponential backoff.
        """

        json_schema = self._convert_schema(
            schema
        )

        max_retries = int(
            os.getenv(
                "MAX_RETRIES",
                "4",
            )
        )

        for size in (6, 4, 2, 1):

            dense = "\n\n".join(
                chunks[:size]
            )

            prompt = (
                "TARGET SCHEMA:\n"
                f"{json.dumps(json_schema, indent=2)}\n\n"
                "SOURCE TEXT:\n"
                f"{dense}"
            )

            for attempt in range(
                max_retries
            ):

                try:

                    result = await self._call(
                        provider=provider,
                        key=key,
                        model=model,
                        prompt=prompt,
                        json_schema=json_schema,
                    )

                    return self._parse_json(
                        result
                    )

                except httpx.HTTPStatusError as e:

                    code = e.response.status_code

                    # -------------------------------------------------
                    # RATE LIMIT / QUOTA
                    # -------------------------------------------------

                    if code == 429:

                        raise RuntimeError(
                            f"{provider} returned "
                            "HTTP 429 rate-limit/quota "
                            "error"
                        )

                    # -------------------------------------------------
                    # PAYLOAD TOO LARGE
                    # -------------------------------------------------

                    if code == 413:

                        print(
                            f"{provider}: payload too large; "
                            "reducing input size"
                        )

                        break

                    # -------------------------------------------------
                    # SERVER ERRORS
                    # -------------------------------------------------

                    if 500 <= code < 600:

                        delay = min(
                            20,
                            (2 ** attempt)
                            + random.random(),
                        )

                        await asyncio.sleep(
                            delay
                        )

                        continue

                    # -------------------------------------------------
                    # OTHER HTTP ERRORS
                    # -------------------------------------------------

                    raise

                except (
                    httpx.TimeoutException,
                    httpx.NetworkError,
                ):

                    if attempt == max_retries - 1:
                        raise

                    delay = min(
                        20,
                        (2 ** attempt)
                        + random.random(),
                    )

                    await asyncio.sleep(
                        delay
                    )

                except Exception as e:

                    # -------------------------------------------------
                    # Gemini SDK errors
                    #
                    # The Google GenAI SDK does not necessarily expose
                    # these as httpx.HTTPStatusError, so inspect the
                    # exception for a status code.
                    # -------------------------------------------------

                    status_code = getattr(
                        e,
                        "status_code",
                        None,
                    )

                    if status_code == 429:

                        raise RuntimeError(
                            f"{provider} returned "
                            "429 rate-limit/quota error"
                        )

                    # Some SDK errors expose a response object.
                    response = getattr(
                        e,
                        "response",
                        None,
                    )

                    if response is not None:

                        response_status = getattr(
                            response,
                            "status_code",
                            None,
                        )

                        if response_status == 429:

                            raise RuntimeError(
                                f"{provider} returned "
                                "429 rate-limit/quota error"
                            )

                    # For provider-specific errors such as
                    # unavailable model, authentication failure,
                    # invalid request, etc., immediately move
                    # to the next provider.

                    raise

        raise RuntimeError(
            "Provider exhausted after retries "
            "and payload reduction: "
            f"{provider}"
        )

    # =========================================================
    # PROVIDER CALL
    # =========================================================

    async def _call(
        self,
        provider: str,
        key: str,
        model: str,
        prompt: str,
        json_schema: dict,
    ):
        """
        Execute one request against the selected provider.
        """

        # =====================================================
        # GEMINI
        # =====================================================

        if provider == "gemini":

            client = genai.Client(
                api_key=key
            )

            try:

                interaction = (
                    await client.aio.interactions.create(
                        model=model,
                        input=prompt,
                        system_instruction=SYSTEM,
                        response_format={
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": json_schema,
                        },
                    )
                )

                output = (
                    interaction.output_text
                )

                if not output:

                    raise RuntimeError(
                        "Gemini returned empty output"
                    )

                return output

            finally:

                await client.aio.aclose()

        # =====================================================
        # GROQ / DEEPSEEK
        # =====================================================

        async with httpx.AsyncClient(
            timeout=int(
                os.getenv(
                    "REQUEST_TIMEOUT",
                    "60",
                )
            )
        ) as client:

            if provider == "groq":

                base_url = (
                    "https://api.groq.com/"
                    "openai/v1/chat/completions"
                )

            elif provider == "deepseek":

                base_url = (
                    "https://api.deepseek.com/"
                    "chat/completions"
                )

            else:

                raise ValueError(
                    f"Unknown provider: {provider}"
                )

            response = await client.post(
                base_url,
                headers={
                    "Authorization": (
                        f"Bearer {key}"
                    ),
                    "Content-Type": (
                        "application/json"
                    ),
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": SYSTEM,
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "response_format": {
                        "type": "json_object"
                    },
                },
            )

            response.raise_for_status()

            data = response.json()

            choices = data.get(
                "choices",
                [],
            )

            if not choices:

                raise RuntimeError(
                    f"{provider} returned no choices"
                )

            message = choices[0].get(
                "message",
                {},
            )

            content = message.get(
                "content"
            )

            if not content:

                raise RuntimeError(
                    f"{provider} returned empty content"
                )

            return content

    # =========================================================
    # SCHEMA CONVERSION
    # =========================================================

    @classmethod
    def _convert_schema(
        cls,
        schema: dict,
    ) -> dict:
        """
        Convert the project's simplified schema into
        standard JSON Schema.
        """

        if not isinstance(
            schema,
            dict,
        ):

            raise TypeError(
                "schema must be a dictionary"
            )

        properties = {}
        required = []

        for field, value in schema.items():

            if isinstance(
                value,
                dict,
            ):

                properties[field] = (
                    cls._convert_schema(
                        value
                    )
                )

            else:

                properties[field] = (
                    cls._descriptor_to_schema(
                        value
                    )
                )

            required.append(field)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    # =========================================================
    # DESCRIPTOR → JSON SCHEMA
    # =========================================================

    @staticmethod
    def _descriptor_to_schema(
        descriptor: Any,
    ) -> dict:
        """
        Convert project descriptors such as:

            string or null
            integer or null
            boolean or null
            FREE|FREEMIUM|PAID|ENTERPRISE|null

        into JSON Schema.
        """

        if not isinstance(
            descriptor,
            str,
        ):

            return {
                "type": "string"
            }

        value = descriptor.strip()

        lower = value.lower()

        # -----------------------------------------------------
        # ENUM
        # -----------------------------------------------------

        if "|" in value:

            parts = [
                part.strip()
                for part in value.split("|")
            ]

            allow_null = any(
                part.lower() == "null"
                for part in parts
            )

            enum_values = [
                part
                for part in parts
                if part.lower() != "null"
            ]

            result = {
                "type": "string",
                "enum": enum_values,
            }

            if allow_null:
                result["enum"].append(
                    None
                )

            return result

        # -----------------------------------------------------
        # STRING / DATE / TIMESTAMP
        # -----------------------------------------------------

        if (
            "string" in lower
            or "timestamp" in lower
            or "iso-8601" in lower
        ):

            if "null" in lower:

                return {
                    "type": [
                        "string",
                        "null",
                    ]
                }

            return {
                "type": "string"
            }

        # -----------------------------------------------------
        # INTEGER
        # -----------------------------------------------------

        if "integer" in lower:

            if "null" in lower:

                return {
                    "type": [
                        "integer",
                        "null",
                    ]
                }

            return {
                "type": "integer"
            }

        # -----------------------------------------------------
        # NUMBER
        # -----------------------------------------------------

        if (
            "number" in lower
            or "float" in lower
        ):

            if "null" in lower:

                return {
                    "type": [
                        "number",
                        "null",
                    ]
                }

            return {
                "type": "number"
            }

        # -----------------------------------------------------
        # BOOLEAN
        # -----------------------------------------------------

        if "boolean" in lower:

            if "null" in lower:

                return {
                    "type": [
                        "boolean",
                        "null",
                    ]
                }

            return {
                "type": "boolean"
            }

        # -----------------------------------------------------
        # FALLBACK
        # -----------------------------------------------------

        return {
            "type": "string"
        }

    # =========================================================
    # JSON PARSER
    # =========================================================

    @staticmethod
    def _parse_json(
        text: str,
    ):
        """
        Parse JSON returned by the provider.
        """

        if isinstance(
            text,
            dict,
        ):
            return text

        if not isinstance(
            text,
            str,
        ):

            raise ValueError(
                "LLM output is not text or JSON"
            )

        text = text.strip()

        if text.startswith(
            "```json"
        ):

            text = text[
                len("```json"):
            ]

        elif text.startswith(
            "```"
        ):

            text = text[
                len("```"):
            ]

        if text.endswith(
            "```"
        ):

            text = text[:-3]

        text = text.strip()

        return json.loads(text)