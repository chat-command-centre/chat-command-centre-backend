from abc import ABC, abstractmethod
from ...utils.triggers import TriggerDispatcherBase


class CloudProviderDispatcherBase(TriggerDispatcherBase, ABC):
    def __init__(self, credentials):
        self.credentials = credentials

    def start(self):
        pass

    def stop(self):
        pass

    def dispatch_event(self, event):
        pass

    @abstractmethod
    def authenticate(self):
        pass

    @abstractmethod
    def monitor_events(self):
        pass
