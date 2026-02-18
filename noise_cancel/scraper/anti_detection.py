from __future__ import annotations

import random


def random_delay(min_s: float = 1.0, max_s: float = 3.0) -> float:
    return random.uniform(min_s, max_s)  # noqa: S311


def human_scroll_sequence(scroll_count: int) -> list[dict]:
    actions = []
    for _ in range(scroll_count):
        direction = "up" if random.random() < random.uniform(0.1, 0.2) else "down"  # noqa: S311
        actions.append({
            "scroll_y": random.randint(300, 800),  # noqa: S311
            "delay": random_delay(1.0, 3.0),
            "direction": direction,
        })
    return actions


def random_viewport() -> dict:
    viewports = [
        (1280, 720),
        (1366, 768),
        (1440, 900),
        (1536, 864),
        (1600, 900),
        (1920, 1080),
        (2560, 1440),
        (1280, 800),
        (1680, 1050),
        (1920, 1200),
    ]
    w, h = random.choice(viewports)  # noqa: S311
    w = max(1024, min(2560, w + random.randint(-10, 10)))  # noqa: S311
    h = max(600, min(1600, h + random.randint(-10, 10)))  # noqa: S311
    return {"width": w, "height": h}
