from dataclasses import dataclass, field


@dataclass
class Call:
    model: str
    system: str
    user: str
    images: list[bytes]
    max_tokens: int
    thinking: bool


@dataclass
class FakeCompleter:
    """Stands in for the NVIDIA API: returns canned responses in order and records every call."""

    responses: list[str]
    input_tokens: int = 10
    output_tokens: int = 5
    calls: list[Call] = field(default_factory=list)

    def __call__(self, model, system, user, images, max_tokens, thinking):
        self.calls.append(Call(model, system, user, images, max_tokens, thinking))
        return self.responses[len(self.calls) - 1], self.input_tokens, self.output_tokens
