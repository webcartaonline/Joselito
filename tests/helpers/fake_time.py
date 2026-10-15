"""A fake clock so countdowns can be tested without really waiting."""


class FakeTime:
    """Replace the ``time`` module in cli: sleeping only moves the clock forward."""

    def __init__(self) -> None:
        """Start the clock at zero."""
        self.now = 0.0
        self.slept = 0.0

    def monotonic(self) -> float:
        """Return the fake current time."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Move the clock forward instead of waiting."""
        self.now += seconds
        self.slept += seconds
