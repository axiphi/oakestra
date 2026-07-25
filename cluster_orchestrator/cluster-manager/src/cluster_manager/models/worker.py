from dataclasses import dataclass
from typing import Optional, Any, List, Dict

from pydantic import ConfigDict, BaseModel, field_validator


class WorkerCsiDriver(BaseModel):
    model_config = ConfigDict(extra="allow")

    csi_driver_name: Optional[str] = None

    @field_validator(
        "csi_driver_name",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value


class WorkerMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    # TODO: I don't think resource-abstractor returns this
    architecture: Optional[str] = None

    vcpus: Optional[int] = None
    memory: Optional[int] = None
    vgpus: Optional[int] = None
    vram: Optional[float] = None

    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    vram_percent: Optional[float] = None
    gpu_temp: Optional[float] = None

    # TODO: I don't think resource-abstractor returns this (only 'gpu_percent')
    gpu_usage: Optional[float] = None

    # TODO: I don't think resource-abstractor returns this (only 'gpu_drivers')
    gpu_driver: Optional[str] = None

    virtualization: List[str] = []
    supported_addons: List[str] = []
    csi_drivers: List[WorkerCsiDriver] = []

    @field_validator(
        "virtualization",
        "supported_addons",
        "csi_drivers",
        mode="before"
    )
    @classmethod
    def none_to_empty_list(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator(
        "architecture",
        "gpu_driver",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value


@dataclass
class AggregatedWorkerMetrics:
    active_nodes: int
    vcpus: int
    memory: int
    vgpus: int
    vram: int

    cpu_percent: float
    memory_percent: float
    vram_percent: float
    gpu_percent: float

    gpu_drivers: List[str]

    virtualization: List[str]
    supported_addons: List[str]
    csi_drivers: List[Any]

    aggregation_per_architecture: Dict[str, "AggregatedWorkerMetrics"]
