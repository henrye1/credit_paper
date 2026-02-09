"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel
from typing import Optional


class AssessmentStartResponse(BaseModel):
    assessment_id: str


class AssessmentStatusResponse(BaseModel):
    assessment_id: str
    phase: str  # "generating" | "review" | "complete" | "error"
    stage: Optional[str] = None
    message: Optional[str] = None
    section_count: Optional[int] = None
    approved_count: Optional[int] = None


class SectionSchema(BaseModel):
    id: str
    title: str
    html: str
    original_html: str
    status: str  # "pending" | "approved"


class SectionsResponse(BaseModel):
    head_html: str
    sections: list[SectionSchema]


class SectionUpdateRequest(BaseModel):
    html: str


class AiUpdateResponse(BaseModel):
    success: bool
    proposed_html: str
    message: str


class AcceptAiRequest(BaseModel):
    proposed_html: str


class FinalizeResponse(BaseModel):
    success: bool
    report_path: Optional[str] = None
    report_name: Optional[str] = None
    message: str


class PipelineRunResponse(BaseModel):
    run_id: str


class PromptSectionSchema(BaseModel):
    title: str
    description: str
    content: str


class PromptDataSchema(BaseModel):
    metadata: dict
    sections: dict[str, PromptSectionSchema]


class PromptSaveRequest(BaseModel):
    sections: dict[str, PromptSectionSchema]


class PromptListItem(BaseModel):
    name: str
    label: str
    section_count: int


class VersionListItem(BaseModel):
    timestamp: str
    display_time: str


class ExampleSchema(BaseModel):
    prefix: str
    display_name: str
    files: list[dict]


class ApiKeysRequest(BaseModel):
    google_api_key: Optional[str] = None
    firecrawl_api_key: Optional[str] = None


class DirectoryInfo(BaseModel):
    label: str
    path: str
    file_count: int
