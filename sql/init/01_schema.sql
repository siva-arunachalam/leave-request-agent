-- PostgreSQL Specific Schema for PTO Tracking (No Triggers)
-- Using SERIAL for auto-incrementing primary keys.
-- Using TIMESTAMP WITH TIME ZONE (TIMESTAMPTZ) for timestamps.

-- Table to store employee information
CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,                     -- Unique identifier (auto-incrementing)
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,                 -- Employee's unique email address
    hire_date DATE NOT NULL,
    initial_pto_allowance_hours NUMERIC(6, 2) DEFAULT 0.00 NOT NULL, -- Initial PTO hours granted upon hire/reset
    is_active BOOLEAN DEFAULT TRUE NOT NULL,            -- Flag for active employment status
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  -- Requires application logic to update on modification
);

-- Index for faster email lookups
CREATE INDEX idx_employees_email ON employees (email);

-- Table to store company-wide holidays
CREATE TABLE holidays (
    holiday_id SERIAL PRIMARY KEY,                      -- Unique identifier (auto-incrementing)
    holiday_name VARCHAR(100) NOT NULL,
    holiday_date DATE UNIQUE NOT NULL,                  -- Ensures no duplicate holiday dates
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  -- Requires application logic to update on modification
);

-- Index for faster holiday date lookups
CREATE INDEX idx_holidays_date ON holidays (holiday_date);

-- Table to store employee PTO requests
CREATE TABLE pto_requests (
    request_id SERIAL PRIMARY KEY,                      -- Unique identifier (auto-incrementing)
    employee_id INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE, -- Link to the employee making the request
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')), -- Request status (controlled values)
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- When the request was submitted
    notes TEXT,                                          -- Optional notes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Requires application logic to update on modification

    CONSTRAINT chk_pto_requests_date_order CHECK (end_date >= start_date) -- Ensures end date is not before start date
);

-- Indexes for common PTO request queries
CREATE INDEX idx_pto_requests_employee_id ON pto_requests (employee_id);
CREATE INDEX idx_pto_requests_status ON pto_requests (status);
CREATE INDEX idx_pto_requests_dates ON pto_requests (start_date, end_date);


-- Table to track all changes to an employee's PTO balance (audit trail)
CREATE TABLE pto_ledger (
    ledger_id SERIAL PRIMARY KEY,                       -- Unique identifier (auto-incrementing)
    employee_id INT NOT NULL REFERENCES employees(employee_id) ON DELETE CASCADE, -- Link to the relevant employee
    transaction_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Timestamp of the balance change
    change_hours NUMERIC(6, 2) NOT NULL,                -- Hours added (positive) or deducted (negative)
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('initial', 'accrual', 'usage', 'adjustment', 'reset', 'correction')), -- Type of balance change (controlled values)
    description TEXT,                                   -- Optional description of the transaction
    related_request_id INT NULL REFERENCES pto_requests(request_id) ON DELETE SET NULL, -- Link to pto_requests if type is 'usage'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    -- No updated_at: ledger entries are immutable.
);

-- Indexes for common PTO ledger queries
CREATE INDEX idx_pto_ledger_employee_id ON pto_ledger (employee_id);
CREATE INDEX idx_pto_ledger_transaction_type ON pto_ledger (transaction_type);
CREATE INDEX idx_pto_ledger_related_request_id ON pto_ledger (related_request_id);

-- Note: Application layer is responsible for updating 'updated_at' columns
-- in 'employees', 'holidays', and 'pto_requests' tables on modification,
-- as database triggers are not used in this schema version.


