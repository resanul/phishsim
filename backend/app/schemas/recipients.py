from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RecipientCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    department: str = ""
    job_title: str = ""
    location: str = ""
    manager: str = ""
    tags: list[str] = Field(default_factory=list)
    custom_attributes: dict = Field(default_factory=dict)
    is_test_address: bool = False


class RecipientOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    department: str
    job_title: str
    location: str
    manager: str
    is_active: bool
    is_excluded: bool
    is_test_address: bool
    tags: list[str]

    class Config:
        from_attributes = True


class RecipientGroupCreate(BaseModel):
    name: str
    description: str = ""


class CSVImportResult(BaseModel):
    total_rows: int
    imported: int
    duplicates_skipped: int
    invalid_skipped: int
    errors: list[str]
