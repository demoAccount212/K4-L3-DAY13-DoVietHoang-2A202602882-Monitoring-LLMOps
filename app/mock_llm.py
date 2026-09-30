from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .incidents import STATE
from .tracing import get_client, observe, tracing_enabled

# Giá per 1M token — cùng công thức với LabAgent._estimate_cost.
INPUT_COST_PER_MTOK = 3.0
OUTPUT_COST_PER_MTOK = 15.0


def estimate_cost_usd(tokens_in: int, tokens_out: int) -> float:
    input_cost = (tokens_in / 1_000_000) * INPUT_COST_PER_MTOK
    output_cost = (tokens_out / 1_000_000) * OUTPUT_COST_PER_MTOK
    return round(input_cost + output_cost, 6)


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str
    ttft_ms: int


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model

    # Child observation cuối của trace tree (loại generation).
    # capture_input/output=False: không gửi nội dung prompt/answer đã điền câu hỏi.
    @observe(name="generation", as_type="generation", capture_input=False, capture_output=False)
    def generate(self, prompt: str) -> FakeResponse:
        started = time.perf_counter()
        time.sleep(0.05)  # mô phỏng thời điểm token đầu tiên sẵn sàng
        ttft_ms = int((time.perf_counter() - started) * 1000)
        time.sleep(0.10)
        input_tokens = max(20, len(prompt) // 4)
        output_tokens = random.randint(80, 180)
        if STATE["cost_spike"]:
            output_tokens *= 4
        answer = (
            "Starter answer. You should improve this output logic and add better quality checks. "
            "Use retrieved context and keep responses concise."
        )
        response = FakeResponse(
            text=answer,
            usage=FakeUsage(input_tokens, output_tokens),
            model=self.model,
            ttft_ms=ttft_ms,
        )

        if tracing_enabled():
            # Ghi model, usage (token) và cost vào generation observation đang mở.
            # Prompt link được truyền từ agent.run qua propagate_attributes(prompt=...).
            get_client().update_current_generation(
                model=response.model,
                usage_details={
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
                cost_details={
                    "total": estimate_cost_usd(
                        response.usage.input_tokens, response.usage.output_tokens
                    )
                },
                metadata={"ttft_ms": response.ttft_ms},
            )
        return response
