"""On-screen decision overlay for GUI runs. One addUserDebugText per line, updated
via replaceItemUniqueId — never re-created per frame, so text can't pile up.
Colors are DARK: the default view is bright sky/tiles, so white text is invisible."""
import pybullet as p


class DebugPanel:
    def __init__(self, base_pos=None, line_gap=0.07):
        self.ids = {}
        self.base = base_pos or [0.55, 0.0, 0.55]
        self.gap = line_gap

    def _line(self, key, text, pos, color=(0, 0, 0), size=2.0):
        if key in self.ids:
            self.ids[key] = p.addUserDebugText(
                text, pos, textColorRGB=list(color), textSize=size,
                replaceItemUniqueId=self.ids[key])
        else:
            self.ids[key] = p.addUserDebugText(
                text, pos, textColorRGB=list(color), textSize=size)

    def update(self, rec, answers):
        nxt = answers.get("next_skill", {})
        risk = (answers.get("risk", {}) or {}).get("score", 0)
        feas = (answers.get("feasibility", {}) or {}).get("score", 0)
        gate = rec["gate"]
        ok = rec["correct"]
        x, y, z = self.base
        lines = [
            ("skill", f"skill: {nxt.get('choice', '?')}", (0, 0, 0)),
            ("conf", f"confidence: {(nxt.get('confidence') or 0):.2f}", (0, 0.35, 0)),
            ("danger", f"danger: {(risk or 0):.2f}", (0.55, 0.1, 0)),
            ("feas", f"feasibility: {(feas or 0):.2f}", (0, 0.1, 0.55)),
            ("gate", f"gate: {gate['action']} ({gate['reason'][:30]})", (0.35, 0.3, 0)),
            ("result", "CORRECT" if ok else "MISS", (0, 0.45, 0) if ok else (0.6, 0, 0)),
        ]
        for i, (key, text, color) in enumerate(lines):
            self._line(key, text, [x, y, z - i * self.gap], color)
