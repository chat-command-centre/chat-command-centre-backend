from .dispatcher_base import CloudProviderDispatcherBase


class AWSTrigger(CloudProviderDispatcherBase):
    def start(self):
        # Start AWS-specific monitoring
        pass

    def dispatch_event(self, event):
        # Dispatch event to EventManager
        event_manager.dispatch(event)


class S3BucketTrigger(AWSTrigger):
    def start(self):
        # Monitor specific S3 bucket events
        pass
