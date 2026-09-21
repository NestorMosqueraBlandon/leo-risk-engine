from datetime import datetime, timezone

from pydantic import BaseModel, Field


class LabelVersion(BaseModel):
    """Version identifier for the dropout label definition.

    Every change to the label rules (what counts as dropout, which
    exit reasons are included, minimum data requirements) must be
    tracked with a new version. This ensures reproducibility of
    historical models and audits.
    """

    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version string (e.g., 1.0.0)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = Field(default="", description="What changed in this version")
    changelog: list[str] = Field(
        default_factory=list,
        description="List of changes made in this version",
    )

    def bump_major(self) -> "LabelVersion":
        major, minor, patch = (int(x) for x in self.version.split("."))
        return LabelVersion(
            version=f"{major + 1}.0.0",
            description=self.description,
            changelog=self.changelog,
        )

    def bump_minor(self) -> "LabelVersion":
        major, minor, patch = (int(x) for x in self.version.split("."))
        return LabelVersion(
            version=f"{major}.{minor + 1}.0",
            description=self.description,
            changelog=self.changelog,
        )

    def bump_patch(self) -> "LabelVersion":
        major, minor, patch = (int(x) for x in self.version.split("."))
        return LabelVersion(
            version=f"{major}.{minor}.{patch + 1}",
            description=self.description,
            changelog=self.changelog,
        )
