from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminAnalyticsModel(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)


class RoleCountResponse(AdminAnalyticsModel):
    role: str
    count: int


class UserAnalyticsResponse(AdminAnalyticsModel):
    total: int
    active: int
    disabled: int
    password_reset_required: int = Field(serialization_alias="passwordResetRequired")
    pending_registrations: int = Field(serialization_alias="pendingRegistrations")
    active_users_30d: int = Field(serialization_alias="activeUsers30d")
    role_counts: list[RoleCountResponse] = Field(serialization_alias="roleCounts")


class AssistantAnalyticsResponse(AdminAnalyticsModel):
    provider: str
    model: str
    api_key_configured: bool = Field(serialization_alias="apiKeyConfigured")
    chat_turns_30d: int = Field(serialization_alias="chatTurns30d")


class SearchAnalyticsResponse(AdminAnalyticsModel):
    provider: str
    model: str
    api_key_configured: bool = Field(serialization_alias="apiKeyConfigured")
    index_status: str = Field(serialization_alias="indexStatus")
    search_runs_30d: int = Field(serialization_alias="searchRuns30d")
    indexed_products: int = Field(serialization_alias="indexedProducts")
    indexed_passages: int = Field(serialization_alias="indexedPassages")
    indexed_requests: int = Field(serialization_alias="indexedRequests")
    failed_assets: int = Field(serialization_alias="failedAssets")


class VoiceAnalyticsResponse(AdminAnalyticsModel):
    model: str
    enabled: bool
    api_key_configured: bool = Field(serialization_alias="apiKeyConfigured")
    sessions_started_30d: int = Field(serialization_alias="sessionsStarted30d")
    users_30d: int = Field(serialization_alias="users30d")


class AuditAnalyticsResponse(AdminAnalyticsModel):
    window_days: int = Field(serialization_alias="windowDays")
    retained_events: int = Field(serialization_alias="retainedEvents")
    events_30d: int = Field(serialization_alias="events30d")
    login_successes_30d: int = Field(serialization_alias="loginSuccesses30d")
    login_failures_30d: int = Field(serialization_alias="loginFailures30d")
    security_events_30d: int = Field(serialization_alias="securityEvents30d")
    configuration_changes_30d: int = Field(serialization_alias="configurationChanges30d")
    coverage_starts_at: datetime | None = Field(serialization_alias="coverageStartsAt")
    retention_limit_reached: bool = Field(serialization_alias="retentionLimitReached")


class ProcessAnalyticsResponse(AdminAnalyticsModel):
    remote_requests_admitted: int = Field(serialization_alias="remoteRequestsAdmitted")
    remote_requests_denied: int = Field(serialization_alias="remoteRequestsDenied")


class AdminAnalyticsDashboardResponse(AdminAnalyticsModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    users: UserAnalyticsResponse
    assistant: AssistantAnalyticsResponse
    search: SearchAnalyticsResponse
    voice: VoiceAnalyticsResponse
    audit: AuditAnalyticsResponse
    process: ProcessAnalyticsResponse
