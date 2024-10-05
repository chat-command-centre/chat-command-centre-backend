import ell
from .models import ActionPlan, ActionStep
from .entities import DataEntry
from typing import Dict, Any
import asyncio

# Initialize EllAI
ell.init(store="./ell_logs", autocommit=True)


@ell.complex(model="gpt-4", response_format=ActionPlan)
async def plan_action(data_entry: DataEntry, metadata: Dict[str, Any]) -> ActionPlan:
    """
    You are an AI assistant that creates detailed action plans based on the given data and context.
    Provide a structured plan with steps and considerations.
    """
    return f"Data: {data_entry.data}\nMetadata: {metadata}\nPlan an appropriate course of action."


async def determine_best_action(data_entry: DataEntry, metadata: Dict[str, Any]):
    # Use EllAI to get a structured action plan
    plan_message = await plan_action(data_entry, metadata)
    action_plan = plan_message.parsed  # This is an instance of ActionPlan

    # Review the plan (you might add human approval here if needed)
    approved = await review_action_plan(action_plan)
    if approved:
        await execute_action_plan(action_plan, data_entry, metadata)
    else:
        print("Action plan was not approved.")


async def review_action_plan(action_plan: ActionPlan) -> bool:
    # Implement any logic to review the plan, e.g., policy checks
    # For demonstration, we'll auto-approve
    return True


async def execute_action_plan(
    action_plan: ActionPlan, data_entry: DataEntry, metadata: Dict[str, Any]
):
    for step in action_plan.steps:
        action = step.description.lower()
        params = step.parameters
        if action == "send sms":
            await send_sms(**params)
        elif action == "send email":
            await send_email(**params)
        elif action == "make call":
            await make_call(**params)
        else:
            print(f"Unknown action: {action}")
        # Optionally add delays or await confirmations between steps
