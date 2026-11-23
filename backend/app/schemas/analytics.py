from pydantic import BaseModel


class ExpenseSummary(BaseModel):
    vehicle_id: int
    total_expenses: float
    total_transactions: int
    average_expense: float


class CategoryExpense(BaseModel):
    category: str
    total_amount: float
    transaction_count: int


class MonthlyExpense(BaseModel):
    year: int
    month: int
    total_amount: float


class YearlyExpense(BaseModel):
    year: int
    total_amount: float


class ServiceTypeExpense(BaseModel):
    service_type: str
    total_amount: float
    transaction_count: int


class VehicleExpenseComparison(BaseModel):
    vehicle_id: int
    vehicle_name: str
    total_expenses: float
