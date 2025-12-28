from abc import ABC, abstractmethod

from core.models import Monitor

class Adapter(ABC):
    @abstractmethod
    def get_monitors(self) -> list[Monitor]:
        pass

    @abstractmethod
    def focus_window(self, window):
        pass

    @abstractmethod
    def resize_window(self, window):
        pass

    @abstractmethod
    def refresh(self):
        pass