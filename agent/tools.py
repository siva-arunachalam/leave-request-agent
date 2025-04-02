import datetime
import os
import httpx
from typing import Optional, List, Dict, Any, Union

# --- Configuration ---
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
# LIGHT_GREY = '\033[37m' 
# RED = '\033[91m'
LIGHT_GREY = '\033[90m'
# LIGHT_GREY = '\033[38;5;254m'
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

async def get_pto_balance(employee_id: int) -> str:
    """
    Retrieves the current available PTO balance in hours for the employee identified in the current session.
    Requires the employee_id to be known for the session.
    Returns the balance as a string description (e.g., 'You have 88.5 hours available.').
    """
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

async def submit_pto_request(employee_id: int, start_date: str, end_date: str, notes: Optional[str] = None) -> str:
    """
    Submits a new PTO request for the employee identified in the current session.
    Requires the employee_id to be known for the session.
    Needs the start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), and optional notes.
    Returns a confirmation or error message.
    """

    print(f"{LIGHT_GREY}[Tool Call] Submitting PTO request for Employee ID: {employee_id} ({start_date} to {end_date})")
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
        print(f"{LIGHT_GREY}[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        return f"Error submitting request for Employee ID {employee_id}: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"{LIGHT_GREY}[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while submitting the request for Employee ID {employee_id}: {e}"

async def list_pto_requests(employee_id: int, status: Optional[str] = None) -> str:
    """
    Lists existing PTO requests for the employee identified in the current session.
    Requires the employee_id to be known for the session.
    Optionally filters by status (e.g., 'pending', 'approved', 'rejected', 'cancelled').
    Returns a summary of the requests or an error message.
    """

    print(f"{LIGHT_GREY}[Tool Call] Listing requests for Employee ID: {employee_id} (Status: {status})")
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
        print(f"{LIGHT_GREY}[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        return f"Error listing requests for Employee ID {employee_id}: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"{LIGHT_GREY}[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while listing requests for Employee ID {employee_id}: {e}"


async def cancel_pto_request(employee_id: int, request_id: int) -> str:
    """
    Cancels a 'pending' PTO request with the specified request_id for the employee identified in the current session.
    Requires the employee_id to be known for the session and the request_id of the request to cancel.
    Returns a confirmation or error message.
    """

    print(f"{LIGHT_GREY}[Tool Call] Cancelling request ID: {request_id} for Employee ID: {employee_id}")
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
        print(f"{LIGHT_GREY}[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        # Provide more specific feedback based on common errors
        if e.response.status_code == 404:
             return f"Could not cancel request: Request ID {request_id} not found or does not belong to Employee ID {employee_id}."
        if e.response.status_code == 400:
             return f"Could not cancel request ID {request_id}: {error_detail}" # e.g., "Only pending requests can be cancelled..."
        return f"Error cancelling request {request_id} for Employee ID {employee_id}: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"{LIGHT_GREY}[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while cancelling request {request_id} for Employee ID {employee_id}: {e}"

async def list_holidays(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """
    Lists company holidays, optionally filtered by start_date (YYYY-MM-DD) and end_date (YYYY-MM-DD).
    Returns a list of holidays or an error message.
    """
    print(f"{LIGHT_GREY}[Tool Call] Listing holidays (Start: {start_date}, End: {end_date})")
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
        print(f"{LIGHT_GREY}[Tool Error] HTTP Status Error: {e.response.status_code} - {error_detail}")
        return f"Error listing holidays: API returned status {e.response.status_code}. Detail: {error_detail}"
    except Exception as e:
        print(f"{LIGHT_GREY}[Tool Error] Unexpected Error: {e}")
        return f"An unexpected error occurred while listing holidays: {e}"

def get_current_date():
    print(f"{LIGHT_GREY}[Tool Call] get_current_date()")
    return datetime.datetime.now()

def get_day_of_week(date: str) -> str:
    """
    Get the day of the week for a given date.
    
    Args:
        date: string in format 'YYYY-MM-DD'
    
    Returns:
        The day of the week as a string name
    """
    print(f"{LIGHT_GREY}[Tool Call] get_day_of_week(date={date})")
    try:
        date = datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Date string must be in format 'YYYY-MM-DD'")
    
    # Get the day of the week (0 = Monday, 6 = Sunday)
    weekday_num = date.weekday()    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return day_names[weekday_num]

def date_add(date: str, num_days: int) -> str:
    """
    Add or subtract days from a given date
    
    Args:
        date: string in format 'YYYY-MM-DD'
        num_days: number of days to add or subtract. use negative number to subtract 
    Returns:
        The date after adding or subtracting
    """
    print(f"{LIGHT_GREY}[Tool Call] date_add(date={date}, num_days={num_days})")
    try:
        date = datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Date string must be in format 'YYYY-MM-DD'")
    
    return date + datetime.timedelta(days=num_days)

def get_nth_weekday_of_month(year: int, month: int, weekday: str, nth: int) -> Optional[datetime.datetime]:
    """
    Get the date for the nth occurrence of a specific weekday in a month.
    
    Args:
        year: The year (e.g., 2024)
        month: The month (1-12)
        weekday: day name string (e.g., 'Monday')
        nth: Which occurrence of the weekday (1st, 2nd, 3rd, etc.)
    
    Returns:
        A datetime object representing the requested date, or None if the date doesn't exist
        (e.g., 5th Monday in a month that only has 4 Mondays)
    
    Examples:
        get_nth_weekday_of_month(2025, 11, 'Wednesday', 4)  # 4th Wednesday of November 2025
    """

    print(f"{LIGHT_GREY}[Tool Call] get_nth_weekday_of_month(year={year}, month={month}, weekday={weekday}, nth={nth})")
    # Validate inputs
    if not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12")
    
    # Handle string weekday names
    weekday_names = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    weekday = weekday_names.get(weekday.lower())
    if weekday is None:
        raise ValueError("Invalid weekday name")
    
    if not 0 <= weekday <= 6:
        raise ValueError("Weekday must be between 0 and 6 (0=Monday, 6=Sunday)")
    
    if nth == 0:
        raise ValueError("nth must be non-zero (positive for counting from start, negative for counting from end)")
    
    # Get the first day of the month
    first_day = datetime.datetime(year, month, 1)
    
    # Find the first occurrence of the specified weekday
    days_until_first = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + datetime.timedelta(days=days_until_first)
    
    # Add weeks to get to the nth occurrence
    target_date = first_occurrence + datetime.timedelta(weeks=nth-1)
        
    # Check if we're still in the same month
    if target_date.month != month:
        return None
        
    return target_date
    

# List of tools available to the LLM
available_tools = [
    get_pto_balance,
    submit_pto_request,
    list_pto_requests,
    cancel_pto_request,
    list_holidays,
    get_current_date,
    get_day_of_week,
    date_add,
    get_nth_weekday_of_month
]
