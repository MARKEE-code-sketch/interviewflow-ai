"""DeepEval adapter using only the explicitly selected Groq judge model."""

import asyncio
import json

from deepeval.models import DeepEvalBaseLLM
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.groq.llm import GroqLLMService


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self, api_key, model):
        self.model_name = model
        self.service = GroqLLMService(
            api_key=api_key,
            settings=GroqLLMService.Settings(
                model=model, temperature=0, max_completion_tokens=2048,
                extra={"reasoning_effort": "low"} if model.startswith("openai/gpt-oss-") else {},
            ),
        )

    def load_model(self):
        return self.service

    def get_model_name(self):
        return self.model_name

    async def a_generate(self, prompt, schema=None):
        instruction = "Evaluate the supplied test data. Return only the requested JSON, without markdown."
        if schema is not None:
            instruction += " JSON schema: " + json.dumps(schema.model_json_schema())
        response = await asyncio.wait_for(self.service.run_inference(
            LLMContext([{"role": "user", "content": prompt}]),
            system_instruction=instruction,
        ), timeout=30)
        if not response:
            raise ValueError("Evaluation judge returned empty output")
        return schema.model_validate_json(response) if schema is not None else response

    def generate(self, prompt, schema=None):
        return asyncio.run(self.a_generate(prompt, schema))
