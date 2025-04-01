import os
import re
import asyncio
import httpx
from typing import Optional, List, Dict, Any

from openai import AzureOpenAI
from pydantic_ai import PydanticAI
from pydantic import BaseModel, Field

# --- Configuration ---
API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")

# --- Agent State ---
# Simple in-memory state for a single session
class SessionState:
    def __init__(self):
        self.employee_id: Optional[int] = None
        self.message_history: List[Dict[str, Any]] = [
            {"role": "system", "content": "You are a helpful HR assistant specializing in PTO management. Be concise. Ask for the Employee ID if needed for an action and you don't have it yet."}
        ]

session_state = SessionState() # Global state for simplicity in this example

# --- Tool Functions (API Wrappers) ---
# Note: These functions now access session_state.employee_id

async def get_pto_balance() -> str:
    """
    Retrieves the current available PTO balance in hours for the employee identified in the current session.
    Requires the employee_id to be known for the session.
    Returns the balance as a string description (e.g., 'You have 88.5 hours available.').
    """
    if session_state.employee_id is None:
        return "I need your Employee ID before I can check your balance. What is your Employee ID?"

    employee_id = session_state.employee_id
    print(f"[Tool Call] Getting balance for Employee ID: {employee_id}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/me/pto/balance",
                params={"override_employee_id": employee_id}
            )
            response.raise_for_status()
            data = response.json()
            return f"Employee ID {employee_id} has {data.get('available_hours', 0.0)} hours of PTO available."
    except httpx.HTTPStatusError as e:
        error_detail = "Unknown error"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except Exception:
            error_detail = e.response.text
        print(f"[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        return f"Error retrieving balance for Employee ID {employee_id}: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while retrieving balance for Employee ID {employee_id}: {e}"

async def submit_pto_request(start_date: str, end_date: str, notes: Optional[str] = None) -> str:
    """
    Submits a new PTO request for the employee identified in the current session.
    Requires the employee_id to be known for the session.
    Needs the start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), and optional notes.
    Returns a confirmation or error message.
    """
    if session_state.employee_id is None:
        return "I need your Employee ID before I can submit a request. What is your Employee ID?"

    employee_id = session_state.employee_id
    print(f"[Tool Call] Submitting PTO request for Employee ID: {employee_id} ({start_date} to {end_date})")
    try:
        async with httpx.AsyncClient() as client:
            payload = {"start_date": start_date, "end_date": end_date, "notes": notes}
            response = await client.post(
                f"{API_BASE_URL}/me/pto/requests",
                params={"override_employee_id": employee_id},
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return f"Successfully submitted PTO request (ID: {data.get('request_id')}) for Employee ID {employee_id} from {start_date} to {end_date}. Status is {data.get('status')}."
    except httpx.HTTPStatusError as e:
        error_detail = "Unknown error"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except Exception:
            error_detail = e.response.text
        print(f"[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        return f"Error submitting request for Employee ID {employee_id}: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while submitting the request for Employee ID {employee_id}: {e}"

async def list_pto_requests(status: Optional[str] = None) -> str:
    """
    Lists existing PTO requests for the employee identified in the current session.
    Requires the employee_id to be known for the session.
    Optionally filters by status (e.g., 'pending', 'approved', 'rejected', 'cancelled').
    Returns a summary of the requests or an error message.
    """
    if session_state.employee_id is None:
        return "I need your Employee ID before I can list your requests. What is your Employee ID?"

    employee_id = session_state.employee_id
    print(f"[Tool Call] Listing requests for Employee ID: {employee_id} (Status: {status})")
    try:
        async with httpx.AsyncClient() as client:
            params = {"override_employee_id": employee_id}
            if status:
                params["status"] = status
            response = await client.get(
                f"{API_BASE_URL}/me/pto/requests",
                params=params
            )
            response.raise_for_status()
            requests = response.json()
            if not requests:
                return f"No PTO requests found for Employee ID {employee_id}" + (f" with status '{status}'." if status else ".")
            summary = f"Found {len(requests)} request(s) for Employee ID {employee_id}" + (f" with status '{status}'" if status else "") + ":\n"
            for req in requests:
                summary += f"- ID: {req['request_id']}, Dates: {req['start_date']} to {req['end_date']}, Status: {req['status']}\n"
            return summary.strip()
    except httpx.HTTPStatusError as e:
        error_detail = "Unknown error"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except Exception:
            error_detail = e.response.text
        print(f"[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        return f"Error listing requests for Employee ID {employee_id}: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while listing requests for Employee ID {employee_id}: {e}"


async def cancel_pto_request(request_id: int) -> str:
    """
    Cancels a 'pending' PTO request with the specified request_id for the employee identified in the current session.
    Requires the employee_id to be known for the session and the request_id of the request to cancel.
    Returns a confirmation or error message.
    """
    if session_state.employee_id is None:
        return "I need your Employee ID before I can cancel a request. What is your Employee ID?"

    employee_id = session_state.employee_id
    print(f"[Tool Call] Cancelling request ID: {request_id} for Employee ID: {employee_id}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_BASE_URL}/me/pto/requests/{request_id}/cancel",
                 params={"override_employee_id": employee_id}
            )
            response.raise_for_status()
            data = response.json()
            return f"Successfully cancelled PTO request ID {request_id} for Employee ID {employee_id}. Status is now {data.get('status')}."
    except httpx.HTTPStatusError as e:
        error_detail = "Unknown error"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except Exception:
            error_detail = e.response.text
        print(f"[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        # Provide more specific feedback based on common errors
        if e.response.status_code == 404:
             return f"Could not cancel request: Request ID {request_id} not found or does not belong to Employee ID {employee_id}."
        if e.response.status_code == 400:
             return f"Could not cancel request ID {request_id}: {error_detail}" # e.g., "Only pending requests can be cancelled..."
        return f"Error cancelling request {request_id} for Employee ID {employee_id}: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while cancelling request {request_id} for Employee ID {employee_id}: {e}"

async def list_holidays(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """
    Lists company holidays, optionally filtered by start_date (YYYY-MM-DD) and end_date (YYYY-MM-DD).
    Returns a list of holidays or an error message.
    """
    print(f"[Tool Call] Listing holidays (Start: {start_date}, End: {end_date})")
    try:
        async with httpx.AsyncClient() as client:
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            response = await client.get(f"{API_BASE_URL}/holidays", params=params)
            response.raise_for_status()
            holidays = response.json()
            if not holidays:
                return "No holidays found" + (f" between {start_date} and {end_date}." if start_date or end_date else ".")
            summary = f"Found {len(holidays)} holiday(s):\n"
            for holiday in holidays:
                summary += f"- {holiday['holiday_date']}: {holiday['holiday_name']}\n"
            return summary.strip()
    except httpx.HTTPStatusError as e:
        error_detail = "Unknown error"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except Exception:
            error_detail = e.response.text
        print(f"[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        return f"Error listing holidays: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while listing holidays: {e}"

# --- PydanticAI Setup ---

# Configure the Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Instantiate PydanticAI with the client
# Note: Adjust model parameter based on your deployment name if needed,
# although Azure client often infers it from the deployment_name passed during calls.
llm = PydanticAI(
    client=client,
    model=deployment_name, # Pass deployment name here
    # Example using Azure client directly might look different depending on pydantic-ai version
    # Check pydantic-ai docs for exact AzureOpenAI integration syntax
)

# List of tools available to the LLM
available_tools = [
    get_pto_balance,
    submit_pto_request,
    list_pto_requests,
    cancel_pto_request,
    list_holidays,
]

# --- Main Interaction Loop ---

async def handle_message(user_message: str):
    """Handles a single user message, manages state, and interacts with LLM/tools."""
    global session_state # Use the global state object

    print(f"\n[User]: {user_message}")
    session_state.message_history.append({"role": "user", "content": user_message})

    # --- Check for Employee ID if not already set ---
    if session_state.employee_id is None:
        print("[Agent] Checking message for Employee ID...")
        match = re.search(r'\b(\d{3,})\b', user_message) # Simple check for 3+ digits
        if match:
            try:
                potential_id = int(match.group(1))
                # Basic validation - adjust range if needed
                if 1 <= potential_id <= 99999:
                    session_state.employee_id = potential_id
                    confirmation_msg = f"Okay, I'll use Employee ID {session_state.employee_id} for this session. How can I help you now?"
                    print(f"[Agent]: {confirmation_msg}")
                    session_state.message_history.append({"role": "assistant", "content": confirmation_msg})
                    return # End turn here, wait for user's actual request
                else:
                     print("[Agent] Potential ID found, but seems out of typical range.")
            except ValueError:
                print("[Agent] Non-integer found where ID might be.")
                pass # Not a valid int or failed validation

    # --- Call LLM with PydanticAI ---
    # PydanticAI's run method should handle the tool execution loop
    try:
        print("[Agent] Thinking...")
        # Pass the current message history and available tools
        # PydanticAI should execute tools automatically if the LLM requests them
        # and if the required arguments (like employee_id) are implicitly available
        # via the tool function accessing session_state.
        response_content = await llm.run(
            messages=session_state.message_history,
            tools=available_tools
        )

        # Check if the response indicates the need for an Employee ID (tool function returned the specific string)
        if isinstance(response_content, str) and "I need your Employee ID" in response_content:
             print(f"[Agent]: {response_content}")
             # Don't add this specific prompt back to history if the tool added it? Or maybe do? Let's add it.
             session_state.message_history.append({"role": "assistant", "content": response_content})
             # The tool itself already returned the prompt, just display it.

        # --- Handle cases where PydanticAI might return structured tool info ---
        # Note: Check PydanticAI documentation for the exact return type of .run()
        # when tool calls happen. It might return the final string directly,
        # or potentially structured data about the calls. Assuming it returns the final string for now.

        elif isinstance(response_content, str):
            print(f"[Agent]: {response_content}")
            session_state.message_history.append({"role": "assistant", "content": response_content})
        else:
             # Handle unexpected response types from PydanticAI if necessary
             print(f"[Agent] Received unexpected response type: {type(response_content)}")
             print(f"[Agent]: {str(response_content)}")
             session_state.message_history.append({"role": "assistant", "content": str(response_content)})


    except Exception as e:
        print(f"[Agent Error] Error during LLM call or tool execution: {e}")
        # Provide a generic error message to the user
        error_message = "Sorry, I encountered an error processing your request."
        print(f"[Agent]: {error_message}")
        session_state.message_history.append({"role": "assistant", "content": error_message})


async def main():
    """Runs the main interactive command-line loop for the agent."""
    print("PTO Management AI Agent")
    print("Type 'quit' or 'exit' to end the session.")
    print("You can start by telling me your Employee ID or making a request.")

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break
            if not user_input.strip():
                continue

            await handle_message(user_input)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred in the main loop: {e}")
            # Optionally reset state or break loop on critical errors


if __name__ == "__main__":
    asyncio.run(main())

