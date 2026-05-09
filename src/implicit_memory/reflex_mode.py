from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReflexController:
    max_actions: int
    cooldown_steps: int
    actions_taken: int = 0
    cooldown_remaining: int = 0
    in_reflex: bool = False

    def can_enter(self) -> bool:
        return self.cooldown_remaining == 0 and self.actions_taken < self.max_actions

    def enter(self) -> bool:
        if not self.can_enter():
            return False
        self.in_reflex = True
        return True

    def record_action(self) -> None:
        if not self.in_reflex:
            return
        self.actions_taken += 1
        if self.actions_taken >= self.max_actions:
            self.exit()

    def exit(self) -> None:
        self.in_reflex = False
        self.cooldown_remaining = self.cooldown_steps

    def tick(self) -> None:
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
        if self.cooldown_remaining == 0 and not self.in_reflex:
            self.actions_taken = 0
