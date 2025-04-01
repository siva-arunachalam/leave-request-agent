import faker
import random
import datetime
import calendar
from dateutil.relativedelta import relativedelta
import holidays as pyholidays
import psycopg2
import os
import time
import sys

# --- Configuration ---
NUM_EMPLOYEES = 100
START_YEAR_HOLIDAYS = 2015
END_YEAR_HOLIDAYS = 2028 # Generate holidays up to this year
MAX_REQUESTS_PER_EMPLOYEE = 5 # Max number of PTO requests per employee
HOURS_PER_WORK_DAY = 8.0
MIN_INITIAL_ALLOWANCE = 80.0
MAX_INITIAL_ALLOWANCE = 160.0
ANNUAL_ACCRUAL_HOURS = 120.0 # Simplified annual accrual amount
CURRENT_DATE = datetime.date.today()
MAX_DB_CONNECTION_RETRIES = 10
DB_RETRY_DELAY_SECONDS = 5

# --- Database Connection Details (from Environment Variables) ---
DB_HOST = os.environ.get("DB_HOST", "db") # Default to service name 'db'
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "pto_app_db")
DB_USER = os.environ.get("DB_USER", "pto_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "changeme")

# --- Initialization ---
fake = faker.Faker()
employee_data = [] # Store generated employee IDs and hire dates (returned from DB)
holiday_dates = set() # Store holiday dates for business day calculation

# --- Helper Functions ---

def get_us_holidays(year):
    """Gets US federal holidays for a given year, handling observed dates."""
    us_hols = pyholidays.US(years=year)
    observed_holidays = set()
    for date, name in sorted(us_hols.items()):
         observed_holidays.add(date)
    return observed_holidays

def is_business_day(date_to_check, holidays_set):
    """Checks if a date is a business day (Mon-Fri and not a holiday)."""
    return date_to_check.weekday() < 5 and date_to_check not in holidays_set

def calculate_business_hours(start_date, end_date, holidays_set):
    """Calculates business hours between two dates, inclusive."""
    if start_date > end_date:
        return 0.0
    total_hours = 0.0
    current_date = start_date
    while current_date <= end_date:
        if is_business_day(current_date, holidays_set):
            total_hours += HOURS_PER_WORK_DAY
        current_date += datetime.timedelta(days=1)
    return total_hours

def connect_db():
    """Connects to the PostgreSQL database with retry logic."""
    retries = 0
    while retries < MAX_DB_CONNECTION_RETRIES:
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            print("Database connection successful.")
            return conn
        except psycopg2.OperationalError as e:
            retries += 1
            print(f"Database connection failed (attempt {retries}/{MAX_DB_CONNECTION_RETRIES}): {e}")
            if retries < MAX_DB_CONNECTION_RETRIES:
                print(f"Retrying in {DB_RETRY_DELAY_SECONDS} seconds...")
                time.sleep(DB_RETRY_DELAY_SECONDS)
            else:
                print("Max database connection retries reached. Exiting.")
                sys.exit(1) # Exit script if connection fails after retries
    return None # Should not be reached if sys.exit works

# --- Main Data Generation and Insertion Logic ---
conn = None # Initialize connection variable
try:
    conn = connect_db()
    if not conn: # Exit if connection failed in connect_db
         sys.exit(1)

    cur = conn.cursor()
    print("Starting data generation and insertion...")

    # 1. Generate and Insert Holidays
    print("Populating Holidays...")
    all_observed_holidays = set()
    holiday_insert_sql = "INSERT INTO holidays (holiday_date, holiday_name) VALUES (%s, %s) ON CONFLICT (holiday_date) DO NOTHING;"
    for year in range(START_YEAR_HOLIDAYS, END_YEAR_HOLIDAYS + 1):
        # Using fixed list for consistency
        # New Year's Day
        cur.execute(holiday_insert_sql, (datetime.date(year, 1, 1), "New Year's Day"))
        # MLK Day
        first_jan = datetime.date(year, 1, 1)
        first_mon = first_jan + datetime.timedelta(days=(0 - first_jan.weekday() + 7) % 7)
        mlk_day = first_mon + datetime.timedelta(weeks=2)
        cur.execute(holiday_insert_sql, (mlk_day, "Martin Luther King, Jr. Day"))
        # Washington's Birthday
        first_feb = datetime.date(year, 2, 1)
        first_mon_feb = first_feb + datetime.timedelta(days=(0 - first_feb.weekday() + 7) % 7)
        pres_day = first_mon_feb + datetime.timedelta(weeks=2)
        cur.execute(holiday_insert_sql, (pres_day, "Washington's Birthday"))
        # Memorial Day
        last_may = datetime.date(year, 5, 31)
        last_mon_may = last_may - datetime.timedelta(days=last_may.weekday())
        cur.execute(holiday_insert_sql, (last_mon_may, "Memorial Day"))
        # Juneteenth
        if year >= 2021:
             cur.execute(holiday_insert_sql, (datetime.date(year, 6, 19), "Juneteenth National Independence Day"))
        # Independence Day
        cur.execute(holiday_insert_sql, (datetime.date(year, 7, 4), "Independence Day"))
        # Labor Day
        first_sep = datetime.date(year, 9, 1)
        first_mon_sep = first_sep + datetime.timedelta(days=(0 - first_sep.weekday() + 7) % 7)
        cur.execute(holiday_insert_sql, (first_mon_sep, "Labor Day"))
        # Columbus Day
        first_oct = datetime.date(year, 10, 1)
        first_mon_oct = first_oct + datetime.timedelta(days=(0 - first_oct.weekday() + 7) % 7)
        col_day = first_mon_oct + datetime.timedelta(weeks=1)
        cur.execute(holiday_insert_sql, (col_day, "Columbus Day"))
        # Veterans Day
        cur.execute(holiday_insert_sql, (datetime.date(year, 11, 11), "Veterans Day"))
        # Thanksgiving Day
        first_nov = datetime.date(year, 11, 1)
        first_thu_nov = first_nov + datetime.timedelta(days=(3 - first_nov.weekday() + 7) % 7)
        thanksgiving = first_thu_nov + datetime.timedelta(weeks=3)
        cur.execute(holiday_insert_sql, (thanksgiving, "Thanksgiving Day"))
        # Christmas Day
        cur.execute(holiday_insert_sql, (datetime.date(year, 12, 25), "Christmas Day"))

        # Store observed holidays for business day calculations later
        all_observed_holidays.update(get_us_holidays(year))
    conn.commit() # Commit after inserting all holidays
    print(f"Inserted holidays for years {START_YEAR_HOLIDAYS}-{END_YEAR_HOLIDAYS}.")


    # 2. Generate and Insert Employees & Initial Ledger Entries
    print(f"Populating {NUM_EMPLOYEES} Employees...")
    employee_insert_sql = """
        INSERT INTO employees (first_name, last_name, email, hire_date, initial_pto_allowance_hours, is_active)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING employee_id, hire_date, is_active;
    """
    ledger_initial_insert_sql = """
        INSERT INTO pto_ledger (employee_id, transaction_date, change_hours, transaction_type, description)
        VALUES (%s, %s, %s, %s, %s);
    """
    ten_years_ago = CURRENT_DATE - relativedelta(years=10)
    for i in range(NUM_EMPLOYEES):
        first_name = fake.first_name()
        last_name = fake.last_name()
        # Ensure unique email with higher probability
        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(100,999)}@{fake.free_email_domain()}"
        hire_date = fake.date_between(start_date=ten_years_ago, end_date=CURRENT_DATE)
        initial_allowance = round(random.uniform(MIN_INITIAL_ALLOWANCE, MAX_INITIAL_ALLOWANCE), 2)
        is_active = random.choice([True] * 8 + [False] * 2) # 80% active

        try:
             cur.execute(employee_insert_sql, (
                 first_name, last_name, email, hire_date, initial_allowance, is_active
             ))
             # Fetch the returned employee_id, hire_date, is_active
             inserted_emp = cur.fetchone()
             if inserted_emp:
                 emp_id, emp_hire_date, emp_is_active = inserted_emp
                 employee_data.append({"id": emp_id, "hire_date": emp_hire_date, "is_active": emp_is_active})

                 # Insert initial ledger entry
                 if initial_allowance > 0:
                     transaction_date = emp_hire_date + datetime.timedelta(days=1) # Day after hire
                     desc = 'Initial PTO allowance upon hiring'
                     cur.execute(ledger_initial_insert_sql, (
                         emp_id, transaction_date, initial_allowance, 'initial', desc
                     ))
             else:
                 print(f"Warning: Failed to retrieve inserted employee data for {email}")

        except psycopg2.Error as e:
             print(f"Error inserting employee {email}: {e}")
             conn.rollback() # Rollback this specific employee insert if needed, or handle differently
             # Consider skipping or logging failed inserts
             continue # Skip to next employee

    conn.commit() # Commit after inserting all employees and initial ledger entries
    print(f"Inserted {len(employee_data)} employees and initial ledger entries.")


    # 3. Generate Simplified Annual Accruals
    print("Populating Simplified Annual Accrual Ledger Entries...")
    ledger_accrual_insert_sql = """
        INSERT INTO pto_ledger (employee_id, transaction_date, change_hours, transaction_type, description)
        VALUES (%s, %s, %s, %s, %s);
    """
    accrual_count = 0
    for emp in employee_data:
        emp_id = emp["id"]
        hire_date = emp["hire_date"]
        start_accrual_year = hire_date.year + 1 if hire_date.month > 1 or hire_date.day > 1 else hire_date.year
        for year in range(start_accrual_year, CURRENT_DATE.year + 1):
            accrual_date = datetime.date(year, 1, 1)
            if accrual_date <= CURRENT_DATE:
                desc = f"Annual accrual for {year}"
                cur.execute(ledger_accrual_insert_sql, (
                    emp_id, accrual_date, ANNUAL_ACCRUAL_HOURS, 'accrual', desc
                ))
                accrual_count += 1
    conn.commit() # Commit after inserting all accruals
    print(f"Inserted {accrual_count} annual accrual ledger entries.")


    # 4. Generate PTO Requests and Usage Ledger Entries
    print("Populating PTO Requests and Usage Ledger Entries...")
    request_insert_sql = """
        INSERT INTO pto_requests (employee_id, start_date, end_date, status, requested_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING request_id;
    """
    ledger_usage_insert_sql = """
        INSERT INTO pto_ledger (employee_id, transaction_date, change_hours, transaction_type, description, related_request_id)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    request_count = 0
    usage_count = 0
    for emp in employee_data:
        if not emp["is_active"]:
            continue

        emp_id = emp["id"]
        hire_date = emp["hire_date"]
        num_requests = random.randint(0, MAX_REQUESTS_PER_EMPLOYEE)

        for _ in range(num_requests):
            max_request_start_offset = (CURRENT_DATE - hire_date).days - 10
            if max_request_start_offset < 1: continue

            start_offset = random.randint(1, max_request_start_offset)
            request_start_date = hire_date + datetime.timedelta(days=start_offset)
            request_duration = random.randint(1, 10)
            request_end_date = request_start_date + datetime.timedelta(days=request_duration - 1)

            if request_end_date > CURRENT_DATE + relativedelta(years=1):
                 continue

            status = random.choice(['approved'] * 6 + ['pending'] * 2 + ['rejected', 'cancelled']) # Higher chance of approved
            requested_at_offset = random.randint(1, start_offset) if start_offset > 1 else 1
            requested_at = request_start_date - datetime.timedelta(days=requested_at_offset)
            notes = fake.sentence(nb_words=10) if random.random() > 0.5 else None

            try:
                cur.execute(request_insert_sql, (
                    emp_id, request_start_date, request_end_date, status, requested_at, notes
                ))
                request_id = cur.fetchone()[0] # Get the generated request_id
                request_count += 1

                if status == 'approved':
                    hours_used = calculate_business_hours(request_start_date, request_end_date, all_observed_holidays)
                    if hours_used > 0:
                        usage_transaction_date = request_start_date # Record usage on the start date
                        desc = f"PTO Used: {request_start_date.strftime('%Y-%m-%d')} to {request_end_date.strftime('%Y-%m-%d')}"
                        cur.execute(ledger_usage_insert_sql, (
                            emp_id, usage_transaction_date, -hours_used, 'usage', desc, request_id
                        ))
                        usage_count += 1
            except psycopg2.Error as e:
                 print(f"Error inserting request or usage for employee {emp_id}: {e}")
                 conn.rollback() # Rollback this request/usage attempt
                 continue # Skip to next request

    conn.commit() # Commit after inserting all requests and usage entries
    print(f"Inserted {request_count} PTO requests and {usage_count} usage ledger entries.")
    print("Data generation and insertion complete.")

except psycopg2.Error as e:
    print(f"Database error during script execution: {e}")
    if conn:
        conn.rollback() # Rollback any pending transaction on error
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()
        print("Database connection closed.")


