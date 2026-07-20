import logging
from collections import defaultdict
from typing import Dict, Any, List, Optional, Callable, TypeAlias, Union

from resource_abstractor_client import candidate_operations

logger = logging.getLogger("cluster_manager")

CLUSTER_FIELDS = {"_id", "ip", "port", "candidate_name", "candidate_location"}

counters = {
    "cpu_percent": 0,
    "memory_percent": 0,
    "vram_percent": 0,
    "gpu_temp": 0,
    "gpu_percent": 0,
}

ResourceValue: TypeAlias = List[Any] | float | int | str
ResourceAccumulator: TypeAlias = Optional[List[Any] | float | int]

ResourceDict: TypeAlias = Dict[str, ResourceValue]
ResourceAggregator: TypeAlias = Union[
    Callable[[ResourceDict, ResourceAccumulator], ResourceAccumulator],
    Callable[[ResourceDict], ResourceAccumulator],
]


def default_aggregator(w: ResourceDict, acc: ResourceAccumulator, key: str) -> ResourceAccumulator:
    val = w.get(key)
    if val is None:
        return acc

    if isinstance(val, (int, float)):
        if key.endswith("_percent") or key.endswith("_average"):
            return average_aggregator(w, acc, key, custom_counter=key)

        res = acc if acc is not None else 0.0
        return res + val


    if acc is None:
        acc = []
    elif not isinstance(acc, list):
        raise RuntimeError("Tried to use non-numeric resource with numeric accumulator")

    if isinstance(val, list):
        acc.extend(val)
        return acc

    acc.append(val)
    return acc

def average_aggregator(w: ResourceDict, acc: ResourceAccumulator, key: str, custom_counter: Optional[str] = None) -> ResourceAccumulator:
    val = w.get(key)

    if val is None:
        return acc

    if isinstance(val, list):
        raise RuntimeError("Tried to use average_aggregator with list resource value")

    float_val = float(val)
    # Skip zero values when averaging
    if float_val == 0.0:
        return acc

    counter_key = custom_counter if custom_counter is not None else key
    if counter_key not in counters:
        counters[counter_key] = 0

    counters[counter_key] += 1
    n = counters[counter_key]

    if acc is None:
        acc = 0.0
    elif isinstance(acc, list):
        raise RuntimeError("Tried to use average_aggregator with list accumulator")

    acc += (float_val - acc) / n

    return acc


def csi_drivers_aggregator(w: ResourceDict, acc: ResourceAccumulator) -> ResourceAccumulator:
    """Merge csi_drivers from a worker into a deduplicated list of driver names.

    Node Engine advertises drivers as objects: {csi_driver_name, csi_driver_endpoint}.
    After aggregation, the cluster reports a flat list of name strings to the root.
    """
    val = w.get("csi_drivers")
    if val is None:
        return acc

    if acc is None:
        acc = []
    elif not isinstance(acc, list):
        raise RuntimeError("Tried to use csi_drivers_aggregator with non-list accumulator")

    if isinstance(val, list):
        for item in val:
            if isinstance(item, dict):
                name = item.get("csi_driver_name")
            elif isinstance(item, str):
                name = item
            else:
                continue
            if name and name not in acc:
                acc.append(name)
    return acc


# canonical resources are resources that are required by the system manager
# this dict contains {resource_name: aggregation_scheme}
# where aggregation scheme outlines how this resource should be aggregated.
# Every aggregation schema is a function that takes an accumulator and a worker
# and returns a new accumulator: acc, w -> acc
canonical_resources: Dict[str, ResourceAggregator] = {
    "cpu_percent": lambda w, acc=0.0: average_aggregator(w, acc, "cpu_percent"),
    "vcpus": lambda w, acc=0: default_aggregator(w, acc, "vcpus"),
    "memory_percent": lambda w, acc=0.0: average_aggregator(w, acc, "memory_percent"),
    "vram": lambda w, acc=0: default_aggregator(w, acc, "vram"),
    "vram_percent": lambda w, acc=0.0: average_aggregator(w, acc, "vram_percent"),
    "gpu_temp": lambda w, acc=0.0: average_aggregator(w, acc, "gpu_temp"),
    "gpu_drivers": lambda w, acc=None: default_aggregator(w, acc, "gpu_drivers"),
    "gpu_percent": lambda w, acc=0.0: average_aggregator(w, acc, "gpu_percent"),
    "vgpus": lambda w, acc=0: default_aggregator(w, acc, "vgpus"),
    "memory": lambda w, acc=0: default_aggregator(w, acc, "memory"),
    "virtualization": lambda w, acc=None: default_aggregator(w, acc, "virtualization"),
    "supported_addons": lambda w, acc=None: default_aggregator(w, acc, "supported_addons"),
    "csi_drivers": lambda w, acc=None: csi_drivers_aggregator(w, acc),
    "active_nodes": lambda w, acc=0: acc if not w else acc + 1,
}


def aggregate_workers(workers: List[ResourceDict]) -> Dict[str, ResourceAccumulator]:
    # reset global counters
    for key in counters.keys():
        counters[key] = 0

    result = {}

    if workers is None:
        return result

    for w in workers:
        # iterate over all worker resources, always collect canonical resources
        keys_to_process = set(w.keys()) | set(canonical_resources.keys())
        keys_to_process -= CLUSTER_FIELDS

        for key in keys_to_process:
            if key in canonical_resources:
                aggregator = canonical_resources[key]
                if key not in result:
                    result[key] = aggregator(w)
                else:
                    result[key] = aggregator(w, result[key])

            else:
                result[key] = default_aggregator(w, result.get(key), key)

    # add cumulative neutral values
    for key, agg in canonical_resources.items():
        if key not in result:
            result[key] = agg({})

    return result



AggregateInfo: TypeAlias = Dict[str, Union[ResourceAccumulator, Dict[str, Dict[str, ResourceAccumulator]]]]


def aggregate_info() -> AggregateInfo:
    workers = candidate_operations.get_candidates(active=True)

    if workers is None:
        return {}

    result: AggregateInfo = aggregate_workers(workers)

    workers_by_arch: Dict[str, List[Dict[str, ResourceValue]]] = defaultdict(list)
    for w in workers:
        arch = w.get("architecture")
        if arch is None:
            continue
        workers_by_arch[arch].append(w)

    result["aggregation_per_architecture"] = {
        arch: aggregate_workers(workers) for arch, workers in workers_by_arch.items()
    }

    return result
