from abc import ABC, abstractmethod

from core.models import Monitor, Window

class Adapter(ABC):
    @abstractmethod
    async def initialize(self):
        pass
    
    @abstractmethod
    def get_monitors(self) -> list[Monitor]:
        pass

    @abstractmethod
    def focus_window(self, window: Window):
        pass

    @abstractmethod
    def resize_window(self, window: Window):
        pass

    @abstractmethod
    def refresh(self):
        pass
    
    @abstractmethod
    def stop(self):
        pass