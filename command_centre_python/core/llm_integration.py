import json
import openai  # Ensure OpenAI API is properly installed and configured
from typing import Any, Dict, Optional
from .event_manager import event_manager
from .utils.triggers import (
    invoke_trigger_by_name,
    SemanticTrigger,
    SemanticTriggerDispatcher,
)
from .models import ActionPlan


async def process_user_input(user_input: str) -> str:
    # Parse user input to create a trigger
    trigger_info = await llm_parse_user_mandate(user_input)
    if trigger_info:
        condition = trigger_info["condition"]
        action_plan_str = trigger_info["action_plan"]
        # Convert action plan string to ActionPlan instance
        action_plan = parse_action_plan(action_plan_str)
        if action_plan:
            trigger = SemanticTrigger(
                condition=condition,
                action=lambda data_entry, metadata: execute_action_plan(
                    action_plan, data_entry, metadata
                ),
            )
            semantic_dispatcher.register_trigger(trigger)
            return "Your request has been set up successfully."
        else:
            return "Failed to parse the action plan."
    else:
        return "I'm sorry, I couldn't understand your request."


def parse_action_plan(action_plan_str: str) -> Optional[ActionPlan]:
    # Attempt to parse the action plan string into an ActionPlan instance
    try:
        action_plan_data = json.loads(action_plan_str)
        action_plan = ActionPlan.parse_obj(action_plan_data)
        return action_plan
    except Exception as e:
        print(f"Error parsing action plan: {e}")
        return None


async def llm_parse_user_mandate(user_input: str) -> Dict[str, Any]:
    # Use OpenAI's API to parse the user mandate
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "As an assistant, parse the user's request into a JSON object with 'condition' and 'action_plan' fields. The action plan should follow the provided schema.",
            },
            {"role": "user", "content": user_input},
        ],
    )
    result = response["choices"][0]["message"]["content"]
    # The assistant should return a JSON with 'condition' and 'action_plan'
    try:
        trigger_info = json.loads(result)
        return trigger_info
    except json.JSONDecodeError:
        return None


async def llm_tool_call(user_input: str) -> str:
    # Call the LLM with function calling capability
    completion = await openai.ChatCompletion.acreate(
        model="gpt-4-0613",
        messages=[{"role": "user", "content": user_input}],
        functions=[
            {
                "name": "invoke_trigger",
                "description": "Invoke a trigger with specified parameters",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trigger_name": {"type": "string"},
                        "params": {"type": "object"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["trigger_name", "params"],
                },
            }
        ],
        function_call="auto",
    )

    message = completion.choices[0].message
    if message.get("function_call"):
        function_name = message["function_call"]["name"]
        arguments = json.loads(message["function_call"]["arguments"])
        result = await invoke_trigger_by_name(
            arguments["trigger_name"],
            arguments["params"],
            arguments.get("metadata", {}),
        )
        return f"Trigger '{arguments['trigger_name']}' invoked successfully."
    else:
        return message["content"]


# ...
