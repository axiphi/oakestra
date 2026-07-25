from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobInstance(BaseModel):
    model_config = ConfigDict(extra="allow")

    instance_number: Optional[int] = None
    status: Optional[str] = None
    status_detail: Optional[str] = None
    public_ip: Optional[str] = Field(alias="publicip", default=None)

    # timestamp in epoch seconds
    last_modified_timestamp: Optional[float] = None

    cpu_percent: Optional[str] = None
    memory_percent: Optional[str] = None
    disk: Optional[str] = None
    logs: Optional[str] = None

    host_ip: Optional[str] = None
    host_port: Optional[int] = None
    worker_id: Optional[str] = None

    @field_validator(
        "status",
        "status_detail",
        "public_ip",
        "cpu_percent",
        "memory_percent",
        "disk",
        "logs",
        "host_ip",
        "worker_id",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    def require_instance_number(self) -> int:
        if not self.instance_number:
            raise RuntimeError("Expected instance to have instance_number")
        return self.instance_number

    def update(self, other: "JobInstance") -> None:
        if other.status is not None:
            self.status = other.status
        if other.status_detail is not None:
            self.status = other.status_detail
        if other.last_modified_timestamp is not None:
            self.last_modified_timestamp = other.last_modified_timestamp
        if other.public_ip is not None:
            self.public_ip = other.public_ip
        if other.cpu_percent is not None:
            self.cpu_percent = other.cpu_percent
        if other.memory_percent is not None:
            self.memory_percent = other.memory_percent
        if other.disk is not None:
            self.disk = other.disk
        if other.logs is not None:
            self.logs = other.logs


class Job(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(alias="_id", default=None)
    job_name: Optional[str] = None
    status: Optional[str] = None
    status_detail: Optional[str] = None
    instance_list: Optional[List[JobInstance]] = None
    virtualization: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def transform_id(cls, value: Any) -> Optional[str]:
        if value is None:
            return value

        if isinstance(value, str):
            return value if value != "" else None

        if isinstance(value, int) or isinstance(value, float):
            return str(value)

        raise ValueError('Unexpected type')

    @field_validator(
        "job_name",
        "status",
        "status_detail",
        "virtualization",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    def require_id(self) -> str:
        if not self.id:
            raise RuntimeError("Expected Job to have _id")
        return self.id

    def require_job_name(self) -> str:
        if not self.job_name:
            raise RuntimeError("Expected Job to have job_name")
        return self.job_name


class JobInstanceResources(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_name: Optional[str] = None
    instance_number: Optional[int] = Field(default=None, alias="instance")
    virtualization: Optional[str] = None
    logs: Optional[str] = None

    # These are explicitly defined as string in Go, but contain numbers or ""
    cpu_percent: Optional[str] = None
    memory_percent: Optional[str] = None
    disk: Optional[str] = None

    @field_validator(
        "job_name",
        "virtualization",
        "logs",
        "cpu_percent",
        "memory_percent",
        "disk",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    def require_job_name(self) -> str:
        if not self.job_name:
            raise RuntimeError("Expected instance resources to have job_name")
        return self.job_name

    def require_instance_number(self) -> int:
        if not self.instance_number:
            raise RuntimeError("Expected instance resources to have instance")
        return self.instance_number
