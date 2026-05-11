"""
Small strategy-style action registry used by hands.execute_action.

Each action is represented by an ActionPlugin. The default implementation
wraps the existing function-based actions, while still allowing new plugins
to be registered without editing the dispatcher itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Protocol


Command = dict[str, object]


class CommandValidationError(ValueError):
    """Raised when a command does not match the expected action contract."""


@dataclass(frozen=True)
class ActionContext:
    """Runtime context passed to action plugins."""

    debug: bool = False


class ActionPlugin(Protocol):
    """Strategy interface for executable assistant actions."""

    name: str
    description: str
    required_fields: tuple[str, ...]
    requires_confirmation: bool

    def execute(self, command: Command, context: ActionContext) -> str:
        """Run the action and return a user-facing result."""


@dataclass
class FunctionActionPlugin:
    """ActionPlugin wrapper for a plain callable."""

    name: str
    handler: Callable[[Command, ActionContext], str]
    description: str = ""
    required_fields: tuple[str, ...] = ()
    requires_confirmation: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def execute(self, command: Command, context: ActionContext) -> str:
        missing = [field for field in self.required_fields if not command.get(field)]
        if missing:
            joined = ", ".join(missing)
            raise CommandValidationError(f"Eksik parametre: {joined}")
        return self.handler(command, context)


class ActionRegistry:
    """Registry that maps action names to ActionPlugin strategies."""

    def __init__(self):
        self._plugins: dict[str, ActionPlugin] = {}
        self._aliases: dict[str, str] = {}

    def register(self, plugin: FunctionActionPlugin) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"Action already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin
        for alias in plugin.aliases:
            self._aliases[alias] = plugin.name

    def get(self, action: str) -> ActionPlugin | None:
        canonical = self._aliases.get(action, action)
        return self._plugins.get(canonical)

    def names(self) -> list[str]:
        return sorted(self._plugins)

    def metadata(self) -> list[Mapping[str, object]]:
        return [
            {
                "name": plugin.name,
                "description": plugin.description,
                "required_fields": plugin.required_fields,
                "requires_confirmation": plugin.requires_confirmation,
            }
            for plugin in self._plugins.values()
        ]

    def register_many(self, plugins: Iterable[FunctionActionPlugin]) -> None:
        for plugin in plugins:
            self.register(plugin)

