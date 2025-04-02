import os
import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

import databases # Use 'databases' library for async DB access
import sqlalchemy # Often used with 'databases' for query building
# Added Query to the import below
from fastapi import FastAPI, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings # For loading settings

# --- Configuration ---

class Settings(BaseSettings):
    """Loads configuration from environment variables."""
    db_host: str = os.environ.get("DB_HOST", "db")
    db_port: int = int(os.environ.get("DB_PORT", 5432))
    db_user: str = os.environ.get("DB_USER", "pto_user")
    db_password: str = os.environ.get("DB_PASSWORD", "changeme")
    db_name: str = os.environ.get("DB_NAME", "pto_app_db")
    # Construct the database URL for asyncpg driver
    database_url: str = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    # Optional: Add a flag to enable/disable override in production
    # allow_employee_override: bool = os.environ.get("ALLOW_EMPLOYEE_OVERRIDE", False)

    class Config:
        # If you use a .env file, uncomment below
        # env_file = ".env"
        pass

settings = Settings()

# --- Database Setup ---

database = databases.Database(settings.database_url)
metadata = sqlalchemy.MetaData()

# Define table structures (matching our schema) for query building
employees_table = sqlalchemy.Table(
    "employees", metadata,
    sqlalchemy.Column("employee_id", sqlalchemy.Integer, primary_key=True),
    # Add other columns if needed for queries
)

pto_ledger_table = sqlalchemy.Table(
    "pto_ledger", metadata,
    sqlalchemy.Column("ledger_id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_id", sqlalchemy.Integer),
    sqlalchemy.Column("change_hours", sqlalchemy.Numeric),
    # Add other columns if needed
)

pto_requests_table = sqlalchemy.Table(
    "pto_requests", metadata,
    sqlalchemy.Column("request_id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("employee_id", sqlalchemy.Integer, index=True), # Added index=True hint
    sqlalchemy.Column("start_date", sqlalchemy.Date),
    sqlalchemy.Column("end_date", sqlalchemy.Date),
    sqlalchemy.Column("status", sqlalchemy.String, index=True), # Added index=True hint
    sqlalchemy.Column("requested_at", sqlalchemy.TIMESTAMP(timezone=True), server_default=sqlalchemy.func.now()),
    sqlalchemy.Column("notes", sqlalchemy.Text, nullable=True),
    sqlalchemy.Column("created_at", sqlalchemy.TIMESTAMP(timezone=True), server_default=sqlalchemy.func.now()),
    sqlalchemy.Column("updated_at", sqlalchemy.TIMESTAMP(timezone=True), server_default=sqlalchemy.func.now()),
)

holidays_table = sqlalchemy.Table(
    "holidays", metadata,
    sqlalchemy.Column("holiday_id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("holiday_name", sqlalchemy.String),
    sqlalchemy.Column("holiday_date", sqlalchemy.Date, index=True), # Added index=True hint
    # Add other columns if needed
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles database connection pool startup and shutdown."""
    print(f"Connecting to database: {settings.database_url.replace(settings.db_password, '********')}")
    await database.connect()
    print("Database connection established.")
    yield # Application runs here
    print("Disconnecting from database...")
    await database.disconnect()
    print("Database connection closed.")

# Create FastAPI app instance with lifespan management
app = FastAPI(lifespan=lifespan, title="PTO Management API")


# --- Pydantic Models (Data Shapes) ---

class PTOBalance(BaseModel):
    available_hours: float = Field(..., description="Total available PTO hours")

class PTORequestIn(BaseModel):
    start_date: datetime.date
    end_date: datetime.date
    notes: Optional[str] = None

class PTORequestOut(BaseModel):
    request_id: int
    employee_id: int
    start_date: datetime.date
    end_date: datetime.date
    status: str
    requested_at: datetime.datetime # Use datetime for TIMESTAMPTZ
    notes: Optional[str] = None

    class Config:
        orm_mode = True # Allows creating model from ORM objects/dict-like records

class HolidayOut(BaseModel):
    holiday_name: str
    holiday_date: datetime.date

    class Config:
        orm_mode = True


# --- Authentication Placeholder / Dependency ---

async def get_current_employee_id(
    # Add an optional query parameter to override the employee ID for testing
    override_employee_id: Optional[int] = Query(None, include_in_schema=(os.environ.get("ALLOW_EMPLOYEE_OVERRIDE", "false").lower() == "true")) # Hide from prod docs unless enabled
) -> int:
    """
    Dependency to get the current employee ID.

    - In a real app, this would validate an auth token (e.g., JWT).
    - For development/testing, it allows overriding the ID via the
      `override_employee_id` query parameter.
    - If no override is provided, it falls back to a default ID (e.g., 1)
      or the ID from the (future) auth token.

    ** WARNING: The override mechanism should be disabled or secured in production! **
    """
    # Optional: Check if override is allowed based on environment setting
    # if override_employee_id is not None and not settings.allow_employee_override:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee ID override not allowed.")

    if override_employee_id is not None:
        print(f"--- DEV MODE: Using override_employee_id: {override_employee_id} ---")
        return override_employee_id

    # TODO: Replace this fallback with actual authentication logic
    # In a real app, decode token here and get employee_id
    default_employee_id = 1
    print(f"--- DEV MODE: No override, using default employee_id: {default_employee_id} ---")
    return default_employee_id


# --- API Endpoints ---

# --- PTO Endpoints ---
pto_tags = ["PTO"]

# NOTE: Endpoints below automatically use the updated get_current_employee_id dependency

@app.get("/me/pto/balance", response_model=PTOBalance, tags=pto_tags)
async def get_my_pto_balance(
    employee_id: int = Depends(get_current_employee_id) # Dependency provides the ID
):
    """Gets the available PTO balance for the specified/authenticated employee."""
    query = sqlalchemy.select(sqlalchemy.func.sum(pto_ledger_table.c.change_hours)).where(
        pto_ledger_table.c.employee_id == employee_id
    )
    result = await database.fetch_one(query)
    available_hours = result[0] if result and result[0] is not None else 0.0
    return PTOBalance(available_hours=float(available_hours))


@app.post("/me/pto/requests", response_model=PTORequestOut, status_code=status.HTTP_201_CREATED, tags=pto_tags)
async def submit_pto_request(
    request_data: PTORequestIn,
    employee_id: int = Depends(get_current_employee_id) # Dependency provides the ID
):
    """Submits a new PTO request for the specified/authenticated employee."""
    if request_data.end_date < request_data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be before start date."
        )

    insert_query = pto_requests_table.insert().values(
        employee_id=employee_id,
        start_date=request_data.start_date,
        end_date=request_data.end_date,
        notes=request_data.notes,
        status='pending',
    ).returning( # Use RETURNING to get the created record back efficiently
        pto_requests_table.c.request_id, pto_requests_table.c.employee_id,
        pto_requests_table.c.start_date, pto_requests_table.c.end_date,
        pto_requests_table.c.status, pto_requests_table.c.requested_at,
        pto_requests_table.c.notes,
    )
    try:
        created_request_record = await database.fetch_one(insert_query)
    except Exception as e:
        print(f"Database error on insert: {e}") # Log the actual error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create PTO request."
        )
    if not created_request_record:
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created PTO request details after insert."
        )
    return created_request_record


@app.get("/me/pto/requests", response_model=List[PTORequestOut], tags=pto_tags)
async def list_my_pto_requests(
    employee_id: int = Depends(get_current_employee_id), # Dependency provides the ID
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date_filter: Optional[datetime.date] = Query(None, alias="start_date"),
    end_date_filter: Optional[datetime.date] = Query(None, alias="end_date"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Lists PTO requests for the specified/authenticated employee, with optional filters."""
    query = sqlalchemy.select(pto_requests_table).where(
        pto_requests_table.c.employee_id == employee_id
    )
    # Apply filters
    if status_filter:
        query = query.where(pto_requests_table.c.status == status_filter)
    if start_date_filter:
        query = query.where(pto_requests_table.c.start_date >= start_date_filter)
    if end_date_filter:
        query = query.where(pto_requests_table.c.start_date <= end_date_filter)

    # Apply ordering and pagination
    query = query.order_by(pto_requests_table.c.start_date.desc()).limit(limit).offset(offset)

    results = await database.fetch_all(query)
    return results


@app.get("/me/pto/requests/{request_id}", response_model=PTORequestOut, tags=pto_tags)
async def get_my_specific_pto_request(
    request_id: int,
    employee_id: int = Depends(get_current_employee_id) # Dependency provides the ID
):
    """Gets details of a specific PTO request belonging to the specified/authenticated employee."""
    query = sqlalchemy.select(pto_requests_table).where(
        pto_requests_table.c.request_id == request_id
    )
    result = await database.fetch_one(query)

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PTO Request not found.")

    # Verify ownership
    if result["employee_id"] != employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PTO Request not found.")

    return result


@app.patch("/me/pto/requests/{request_id}/cancel", response_model=PTORequestOut, tags=pto_tags)
async def cancel_my_pto_request(
    request_id: int,
    employee_id: int = Depends(get_current_employee_id) # Dependency provides the ID
):
    """Cancels a 'pending' PTO request belonging to the specified/authenticated employee."""
    async with database.transaction(): # Wrap in transaction for atomicity
        # 1. Fetch the request
        select_query = sqlalchemy.select(pto_requests_table).where(
            pto_requests_table.c.request_id == request_id
        )
        result = await database.fetch_one(select_query)

        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PTO Request not found.")

        # 2. Verify ownership
        if result["employee_id"] != employee_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PTO Request not found.") # Hide existence

        # 3. Verify status is 'pending'
        if result["status"] != 'pending':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only 'pending' requests can be cancelled. Current status: {result['status']}."
            )

        # 4. Update the status to 'cancelled'
        update_query = pto_requests_table.update().where(
            pto_requests_table.c.request_id == request_id
        ).values(
            status='cancelled',
            updated_at=datetime.datetime.now(datetime.timezone.utc) # Explicitly set updated_at
        ).returning( # Return the updated record
             pto_requests_table.c.request_id, pto_requests_table.c.employee_id,
             pto_requests_table.c.start_date, pto_requests_table.c.end_date,
             pto_requests_table.c.status, pto_requests_table.c.requested_at,
             pto_requests_table.c.notes,
        )

        updated_request_record = await database.fetch_one(update_query)

        if not updated_request_record:
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update PTO request after cancellation."
            )

        return updated_request_record


# --- Holidays Endpoint ---
holidays_tags = ["Holidays"]

@app.get("/holidays", response_model=List[HolidayOut], tags=holidays_tags)
async def list_company_holidays(
    start_date_filter: Optional[datetime.date] = Query(None, alias="start_date"),
    end_date_filter: Optional[datetime.date] = Query(None, alias="end_date"),
):
    """Lists company holidays, optionally filtered by date range."""
    query = sqlalchemy.select(holidays_table)

    if start_date_filter:
        query = query.where(holidays_table.c.holiday_date >= start_date_filter)
    if end_date_filter:
        query = query.where(holidays_table.c.holiday_date <= end_date_filter)

    query = query.order_by(holidays_table.c.holiday_date)

    results = await database.fetch_all(query)
    return results


# --- Root endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint providing a welcome message."""
    return {"message": "Welcome to the PTO Management API"}


