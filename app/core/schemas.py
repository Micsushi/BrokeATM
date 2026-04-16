from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParsedRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_date: date | None
    posted_date: date | None = None
    reference_number: str | None = None
    merchant_name: str = ""
    merchant_city: str | None = None
    merchant_state: str | None = None
    merchant_country: str | None = None
    mcc_description: str | None = None
    amount: float
    currency: str = "CAD"
    transaction_type: str
    suggested_category: str | None = None
    category_name: str | None = None
    card_number_masked: str | None = None
    cardholder: str | None = None
    is_payment: bool = False
    is_refund: bool = False
    duplicate: bool = False
    exclude: bool = False
    notes: str | None = None
    source_file: str | None = None
    import_month: int | None = None
    import_year: int | None = None
    normalized_merchant: str | None = None
    keyword_matches: list[dict[str, Any]] = Field(default_factory=list)
    keyword_resolution_needed: bool = False
    keyword_conflict_categories: bool = False
    suggestion_source: str | None = None


class ParseResponse(BaseModel):
    format: str | None
    rows: list[ParsedRow]
    detected_month: int | None
    detected_year: int | None
    errors: list[str]
    col_map: dict[str, str] = Field(default_factory=dict)


class ParserResult(BaseModel):
    parser_id: str
    parser_label: str
    confidence: float
    rows: list[ParsedRow]
    skipped_rows: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    unknown_pdf_categories: list[str] = Field(default_factory=list)


class CommitRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_date: date
    posted_date: date | None = None
    reference_number: str | None = None
    merchant_name: str = ""
    merchant_city: str | None = None
    merchant_state: str | None = None
    merchant_country: str | None = None
    mcc_description: str | None = None
    amount: float
    currency: str = "CAD"
    transaction_type: str
    category_name: str | None = None
    card_number_masked: str | None = None
    cardholder: str | None = None
    exclude: bool = False
    notes: str | None = None
    source_file: str | None = None
    import_month: int | None = None
    import_year: int | None = None


class CommitRequest(BaseModel):
    filename: str
    month: int
    year: int
    rows: list[CommitRow]


class CommitResponse(BaseModel):
    batch_id: str
    batch_ids: list[str] = Field(default_factory=list)
    imported: int
    skipped: int


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_date: date
    posted_date: date | None
    reference_number: str | None
    merchant_name: str
    merchant_city: str | None
    merchant_state: str | None
    merchant_country: str | None
    mcc_description: str | None
    amount: float
    currency: str
    transaction_type: str
    account_id: int | None
    category_id: int | None
    notes: str | None
    import_batch_id: str | None
    is_excluded: bool
    created_at: datetime
    updated_at: datetime
    exact_duplicate: bool = False
    category_name: str | None = None
    account_name: str | None = None


class TransactionCreate(BaseModel):
    transaction_date: date
    merchant_name: str
    amount: float
    transaction_type: str = "expense"
    category_id: int | None = None
    account_id: int | None = None
    notes: str | None = None
    currency: str = "CAD"
    posted_date: date | None = None
    merchant_city: str | None = None
    merchant_country: str | None = None


class TransactionUpdate(BaseModel):
    merchant_name: str | None = None
    amount: float | None = None
    transaction_type: str | None = None
    category_id: int | None = None
    account_id: int | None = None
    notes: str | None = None
    is_excluded: bool | None = None
    transaction_date: date | None = None


class BulkDeleteRequest(BaseModel):
    ids: list[int]


class BulkUpdateRequest(BaseModel):
    ids: list[int]
    category_id: int | None = None
    transaction_type: str | None = None


class TransactionListResponse(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int


class DuplicateGroupOut(BaseModel):
    keep_id: int
    transaction_ids: list[int]
    row_count: int
    summary: dict[str, Any]


class DuplicateReportResponse(BaseModel):
    groups: list[DuplicateGroupOut]
    total_groups: int
    total_extra_rows: int


class PruneExactDuplicatesRequest(BaseModel):
    confirm: bool = False


class PruneExactDuplicatesResponse(BaseModel):
    deleted: int


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None
    keywords: str | None
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str
    color: str | None = None
    keywords: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    keywords: str | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    card_number_masked: str | None
    institution: str | None
    created_at: datetime


class AccountCreate(BaseModel):
    name: str
    card_number_masked: str | None = None
    institution: str | None = None


class PieSlice(BaseModel):
    category: str
    amount: float
    color: str | None = None


class BarMonth(BaseModel):
    month: int
    year: int
    label: str
    expenses: float
    income: float


class DashboardResponse(BaseModel):
    expense_pie: list[PieSlice]
    income_pie: list[PieSlice]
    bar_chart: list[BarMonth]
    total_expenses: float
    total_income: float
    net: float


class LargeExpenseRow(BaseModel):
    id: int
    transaction_date: date
    merchant_name: str
    category: str | None
    amount: float
    pct_of_total: float
    currency: str


class LargeExpensesResponse(BaseModel):
    items: list[LargeExpenseRow]
    total: int
    page: int
    page_size: int


class BudgetCategoryRule(BaseModel):
    category_id: int
    limit_amount: float


class BudgetSave(BaseModel):
    total: float | None = None
    rules: list[BudgetCategoryRule] = []


class BudgetCategoryAvg(BaseModel):
    category_id: int | None
    category_name: str
    category_color: str | None = None
    avg_monthly: float
    avg_6m: float = 0.0
    avg_3m: float = 0.0
    avg_1m: float = 0.0
    limit_amount: float | None = None


class BudgetSettingsOut(BaseModel):
    total: float | None
    avg_months: int
    categories: list[BudgetCategoryAvg]


class BudgetMonthItem(BaseModel):
    category_id: int | None
    category_name: str
    category_color: str | None = None
    budget: float | None
    spent: float
    over: bool


class BudgetMonthSummary(BaseModel):
    ym: str
    label: str
    total_budget: float | None
    total_spent: float
    others_spent: float
    items: list[BudgetMonthItem]


class BudgetSummaryResponse(BaseModel):
    months: int
    total_budget: float | None
    monthly: list[BudgetMonthSummary]


class AppSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    default_currency: str


class AppSettingsUpdate(BaseModel):
    default_currency: str


class RecurringRuleCreate(BaseModel):
    merchant_name: str
    amount: float
    transaction_type: str = "expense"
    currency: str = "CAD"
    category_id: int | None = None
    account_id: int | None = None
    notes: str | None = None
    frequency: str  # monthly, weekly, biweekly, yearly
    start_date: date
    end_date: date | None = None


class RecurringRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_name: str
    amount: float
    transaction_type: str
    currency: str
    category_id: int | None
    account_id: int | None
    notes: str | None
    frequency: str
    start_date: date
    end_date: date | None
    last_created_date: date | None
    created_at: datetime


class ProcessRecurringResponse(BaseModel):
    created: int
    rules_triggered: int
