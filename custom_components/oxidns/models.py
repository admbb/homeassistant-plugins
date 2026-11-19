"""Pure, testable conversions for OxiDNS measurements."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

METRIC = re.compile(r"^([a-zA-Z_:][\w:]*)\{([^}]*)\}\s+([-+\deE.]+)(?:\s|$)")
LABEL = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"')


def metrics(text: str, tag: str) -> dict[str, float]:
    """Extract only a selected collector; never add multiple observation points."""
    result = {}
    for line in text.splitlines():
        match = METRIC.match(line)
        if not match:
            continue
        name, raw_labels, value = match.groups()
        labels = dict(LABEL.findall(raw_labels))
        if labels.get("plugin_tag") == tag:
            try:
                number = float(value)
            except ValueError:
                continue
            if math.isfinite(number):
                result[name] = number
    return result


@dataclass
class Rate:
    """Counter rate using monotonic time; resets never generate negative rates."""

    previous: float | None = None
    when: float | None = None
    instance: str | None = None

    def update(self, count: float | None, now: float, instance: str | None) -> float | None:
        if count is None:
            self.previous, self.when, self.instance = None, None, instance
            return None
        result = None
        if (
            self.previous is not None
            and self.when is not None
            and now > self.when
            and count >= self.previous
            and self.instance == instance
        ):
            result = (count - self.previous) / (now - self.when)
        self.previous, self.when, self.instance = count, now, instance
        return result


def record_summary(record: dict) -> dict:
    """Allowlist event fields, excluding response bodies and execution steps."""
    questions = record.get("questions_json") or []
    question = questions[0] if questions and isinstance(questions[0], dict) else {}
    return {
        "id": record.get("id"),
        "created_at_ms": record.get("created_at_ms"),
        "client_ip": record.get("client_ip"),
        "qname": question.get("name"),
        "qtype": question.get("qtype"),
        "rcode": record.get("rcode"),
        "elapsed_ms": record.get("elapsed_ms"),
        "answer_count": record.get("answer_count"),
    }
