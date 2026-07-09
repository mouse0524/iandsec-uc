from pydantic import BaseModel, Field, field_validator


class ReleaseRecordIn(BaseModel):
    id: int | None = None
    product: str = Field(..., max_length=120)
    version: str = Field(..., max_length=80)
    channel: str = Field(default="正式版本", max_length=30)
    status: str = Field(default="待发布", max_length=30)
    publishDate: int | None = None
    publishDateText: str | None = Field(default=None, max_length=40)
    serverVersion: str | None = Field(default=None, max_length=80)
    windowsVersion: str | None = Field(default=None, max_length=80)
    linuxVersion: str | None = Field(default=None, max_length=80)
    macVersion: str | None = Field(default=None, max_length=80)
    mobileVersion: str | None = Field(default=None, max_length=80)
    packagePath: str = Field(..., max_length=500)
    packageNote: str | None = Field(default=None, max_length=120)
    footerNote: str | None = Field(default=None, max_length=200)
    highlightsText: str | None = Field(default=None, max_length=20000)
    fixesText: str | None = Field(default=None, max_length=20000)
    detailsText: str | None = Field(default=None, max_length=50000)

    @field_validator("product", "version", "packagePath")
    @classmethod
    def validate_required_text(cls, value: str):
        text = str(value or "").strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator(
        "channel",
        "status",
        "serverVersion",
        "windowsVersion",
        "linuxVersion",
        "macVersion",
        "mobileVersion",
        "packageNote",
        "footerNote",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ReleaseRecordDeleteIn(BaseModel):
    id: int
