# Command Centre Python Documentation

Welcome to the **Command Centre Python** documentation. This package serves as a modular and extensible framework designed to integrate various services, manage events, and facilitate system operations in a centralized manner.

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
  - [Entities Module](#entities-module)
  - [Event Manager](#event-manager)
  - [System Module](#system-module)
- [Modules](#modules)
  - [AI/ML Integrations](#aiml-integrations)
  - [Analytics & Monitoring](#analytics--monitoring)
  - [Calendar Module](#calendar-module)
  - [Cloud Storage Integrations](#cloud-storage-integrations)
  - [Voice Control Module](#voice-control-module)
  - [System Events Module](#system-events-module)
  - [File & Document Management](#file--document-management)
  - [IoT Automation Module](#iot-automation-module)
- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Command Centre Python is designed to help developers create a centralized command center for managing various services and integrations. It provides a robust event-driven architecture, allowing for seamless integration with different triggers, services, and systems.

Key features include:

- Modular design for easy extension and maintenance
- Event management system for handling triggers and listeners
- Service management for starting and stopping integrated services
- Integrations with popular AI/ML platforms, cloud storage, analytics tools, and more

---

## Core Components

### Entities Module

Located at `command_centre_python/core/entities.py`, this module defines the core entities used throughout the system.

#### `EntityBase`

- Base class for all entities in the system.
- Attributes:
  - `name`: The name of the entity.
  - `description`: A brief description of the entity.

#### `DataSource`

- Inherits from `EntityBase`.
- Represents a source of data.
- Relationships:
  - `data_entries`: A list of `DataEntry` objects associated with the data source.

#### `DataEntry`

- Inherits from `EntityBase`.
- Represents an entry of data within a data source.
- Attributes:
  - `data`: A dictionary containing the data fields.
- Relationships:
  - `data_source`: The `DataSource` it belongs to.

#### `Event`

- Inherits from `EntityBase`.
- Represents an event in the system.
- Attributes:
  - `status`: The current status of the event (e.g., "pending", "active", "success", "failure").
  - `timestamp`: The timestamp when the event was created.
- Relationships:
  - `parent`: Optional parent event, allowing for event hierarchies.

#### `Service`

- Inherits from `EntityBase`.
- Represents a service that can be started or stopped.
- Attributes:
  - `state`: The current state of the service ("running" or "stopped").
- Methods:
  - `start()`: Starts the service.
  - `stop()`: Stops the service.

#### `Context`

- Inherits from `EntityBase`.
- Represents the context or environment in which the system operates.
- Attributes:
  - `secrets`: A dictionary of secret keys and values.
  - `variables`: A dictionary of environment variables.
- Relationships:
  - `system`: The `SystemBase` it is associated with.

### Event Manager

Located at `command_centre_python/core/event_manager.py`, this module handles the centralized management of events.

#### `Event`

- Base class for all custom events.

#### `EventManager`

- Manages event listeners and triggers.
- Attributes:
  - `listeners`: A dictionary mapping event types to lists of listener callbacks.
  - `triggers`: A list of registered triggers.
- Methods:
  - `register_trigger(trigger)`: Registers a new trigger.
  - `unregister_trigger(trigger)`: Unregisters an existing trigger.
  - `add_listener(event_type, callback)`: Adds a listener for a specific event type.
  - `remove_listener(event_type, callback)`: Removes a listener for a specific event type.
  - `dispatch(event)`: Dispatches an event to all its listeners.
  - `stop_all_triggers()`: Stops all registered triggers.

### System Module

Located at `command_centre_python/core/system.py`, this module defines the system and service management classes.

#### `ServiceManager`

- Inherits from `Service`.
- Manages a collection of services.
- Attributes:
  - `services`: A list of `Service` objects.
- Methods:
  - `start()`: Starts all managed services.
  - `stop()`: Stops all managed services.

#### `SystemBase`

- Inherits from `ServiceManager` and `EntityBase`.
- Represents the base system with event management capabilities.
- Attributes:
  - `event_manager`: An instance of `EventManager`.
- Methods:
  - `start()`: Starts the system and its services.
  - `stop()`: Stops the system and its services.

#### `System`

- Inherits from `SystemBase`.
- Placeholder for system-specific methods and properties.

---

## Modules

### AI/ML Integrations

Located at `command_centre_python/modules/ai_ml/`, this module provides integrations with various AI and machine learning platforms.

#### Supported Integrations:

- **OpenAI** (`openai.py`)
  - Provides methods to interact with OpenAI's GPT models.
  - Example usage:
    ```python
    from command_centre_python.modules.ai_ml.openai import OpenAIIntegration

    openai_integration = OpenAIIntegration(api_key="your_api_key")
    response = openai_integration.generate_text(prompt="Hello, world!")
    ```

- **Azure AI** (`azure_ai.py`)
- **Google AI Platform** (`google_ai_platform.py`)
- **IBM Watson** (`ibm_watson.py`)
- **TensorFlow** (`tensorflow.py`)

### Analytics & Monitoring

Located at `command_centre_python/modules/analytics_monitoring/`, this module integrates with analytics and monitoring tools.

#### Supported Integrations:

- **Datadog** (`datadog.py`)
- **Elastic Stack** (`elastic_stack.py`)
- **Grafana** (`grafana.py`)
- **New Relic** (`new_relic.py`)
- **Prometheus** (`prometheus.py`)

### Calendar Module

Located at `command_centre_python/modules/calendar/`, this module provides calendar event triggers and integrations.

#### `CalendarEventTrigger`

- Trigger based on calendar events.
- Checks for events and dispatches triggers accordingly.

#### `CalendarEventTriggerDispatcher`

- Manages polling the calendar for events.
- Attributes:
  - `update_interval`: Interval between polls (in seconds).
  - `credentials`: Authentication credentials for the calendar service.
  - `calendar_id`: Calendar identifier (default is "primary").
- Methods:
  - `start()`: Starts the dispatcher.
  - `stop()`: Stops the dispatcher.

### Cloud Storage Integrations

Located at `command_centre_python/modules/cloud_storage/`, this module provides integrations with cloud storage services.

#### Supported Integrations:

- **AWS S3** (`aws_s3.py`)
- **Azure Blob Storage** (`azure_blob_storage.py`)
- **Dropbox** (`dropbox.py`)
- **Box** (`box.py`)
- **OneDrive** (`onedrive.py`)

### Voice Control Module

Located at `command_centre_python/modules/voice_control/`, this module enables voice command capabilities.

- Integrates with voice recognition services to interpret voice commands.
- Can dispatch events or execute actions based on voice input.

### System Events Module

Located at `command_centre_python/modules/system_events/`, this module handles system-level events.

- Monitors system resources, logs, and other system-related metrics.
- Can trigger events based on resource usage thresholds or specific system events.

### File & Document Management

Located at `command_centre_python/modules/file_document_management/`, this module manages files and documents.

- Provides functionalities for file operations like reading, writing, and monitoring changes.
- Can integrate with document management systems.

### IoT Automation Module

Located at `command_centre_python/modules/iot_automation/`, this module handles IoT device integration and automation.

- Connects with IoT devices and sensors.
- Allows for automation rules and triggers based on IoT events.


## Getting Started

### Installation

To install Command Centre Python, you can clone the repository and install the required dependencies.

```bash
git clone https://github.com/yourusername/command_centre_python.git
cd command_centre_python
pip install -r requirements.txt
```

Starting the application:

```bash
python -m command_centre_python
```

Example of initializing and starting the system:

```python
from command_centre_python import System
system = System(name="My Command Centre", description="Centralized system management")
system.start()
```
