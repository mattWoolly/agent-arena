"""LiteLLM proxy callback: one JSON line per completed request.

The proxy's Anthropic-format translation drops cached-token counts (LiteLLM
issues 27763/9812), so the harness can't price proxied runs from transcripts.
This callback writes what LiteLLM knows before translation, timestamped, to
.proxy/usage.jsonl; metrics.py can sum a run's window from it.
"""
import json
import os
import time

from litellm.integrations.custom_logger import CustomLogger

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".proxy", "usage.jsonl")


class UsageLogger(CustomLogger):
    def _write(self, kwargs, response_obj):
        slo = kwargs.get("standard_logging_object") or {}
        rec = {
            "ts": time.time(),
            "model": slo.get("model"),
            "response_cost": slo.get("response_cost"),
            "prompt_tokens": slo.get("prompt_tokens"),
            "completion_tokens": slo.get("completion_tokens"),
        }
        try:
            usage = getattr(response_obj, "usage", None)
            if usage is not None:
                rec["raw_usage"] = json.loads(usage.model_dump_json())
        except Exception:
            pass
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs, response_obj)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs, response_obj)


usage_logger = UsageLogger()
