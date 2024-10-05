import logging
from typing import List
from pydantic import Field
import ell
from .entities import EntityBase, Service
from .event_manager import EventManager
from .utils.triggers import SemanticTriggerDispatcher
from ..modules.cloud_providers.aws_dispatcher import AWSDispatcher
from ..modules.cloud_providers.aws_s3_trigger import AWSS3Trigger

logger = logging.getLogger(__name__)


class ServiceManager(Service):
    services: List[Service] = Field(default_factory=list)

    def start(self):
        logger.info("Starting services...")
        for service in self.services:
            service.start()

    def stop(self):
        logger.info("Stopping services...")
        for service in self.services:
            service.stop()


class SystemBase(ServiceManager, EntityBase):
    event_manager: EventManager = Field(default_factory=EventManager)

    def start(self):
        logger.info("Starting system...")
        super().start()

    def stop(self):
        logger.info("Stopping system...")
        self.event_manager.stop_all_triggers()
        super().stop()


class System(SystemBase):
    # Additional system-specific methods and properties
    pass


# Initialize EllAI
ell.init(store="./ell_logs", autocommit=True)

event_manager = EventManager()
semantic_dispatcher = SemanticTriggerDispatcher(event_manager)

# Initialize AWS Dispatcher
aws_dispatcher = AWSDispatcher(
    aws_access_key_id="YOUR_ACCESS_KEY",
    aws_secret_access_key="YOUR_SECRET_KEY",
    region_name="YOUR_REGION",
)
aws_dispatcher.event_manager = event_manager
aws_dispatcher.authenticate()
aws_dispatcher.start()

# Create and register AWS S3 Trigger
s3_trigger = AWSS3Trigger(
    dispatcher=aws_dispatcher,
    bucket_name="your-bucket-name",
    event_type="ObjectCreated",
)
event_manager.register_trigger(s3_trigger)
