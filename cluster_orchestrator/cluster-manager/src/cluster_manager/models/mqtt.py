from typing import Optional, Any, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .job import JobInstanceResources


class NodeInformationMessage(BaseModel):
    model_config = ConfigDict(extra="allow")


class NodeJobMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_name: Optional[str] = Field(alias="sname", default=None)
    status: Optional[str] = None
    status_detail: Optional[str] = None
    instance_number: int = Field(alias="instance")
    public_ip: Optional[str] = Field(alias="publicip", default=None)

    @field_validator(
        "job_name",
        "status",
        "status_detail",
        "public_ip",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value


class NodeJobResourceMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    instance_resources: List[JobInstanceResources] = Field(alias="services", default=[])
