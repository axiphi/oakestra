import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Any

from oakestra_utils.types.statuses import (
    DeploymentStatus,
    LegacyStatus,
    NegativeSchedulingStatus,
    PositiveSchedulingStatus,
    convert_to_status,
)
from resource_abstractor_client import candidate_operations, job_operations
from ..ext_requests.scheduler_requests import scheduler_request_deploy
from ..models.job import Job, JobInstance, JobInstanceResources

logger = logging.getLogger("cluster_manager")


def mark_inactive_as_failed(time_interval_seconds: int) -> None:
    cutoff: float = (datetime.now(timezone.utc) - timedelta(seconds=time_interval_seconds)).timestamp()
    query: Any = {
        "instance_list": {
            "$elemMatch": {
                "$or": [
                    {"last_modified_timestamp": {"$lt": cutoff}},
                ]
            }
        }
    }

    job_objs: List[Any] = job_operations.get_jobs(**query)
    if job_objs is None:
        return

    jobs: List[Job] = [Job.model_validate(job_obj) for job_obj in job_objs]

    for job in jobs:
        job_id: str = job.require_id()
        job_status: Any = convert_to_status(job.status) if job.status is not None else LegacyStatus.LEGACY_0

        all_instances: List[JobInstance] = job.instance_list if job.instance_list is not None else []
        failed_instance_numbers: List[int] = []
        for instance in all_instances:
            instance_number: int = instance.require_instance_number()

            timestamp = (
                instance.last_modified_timestamp if instance.last_modified_timestamp is not None
                else datetime.now(timezone.utc).timestamp()
            )

            if (
                    timestamp < cutoff
                    and job_status not in PositiveSchedulingStatus
                    and job_status != DeploymentStatus.COMPLETED
            ):
                update_instance(
                    job_id,
                    instance_number,
                    JobInstance(status=DeploymentStatus.FAILED.value, status_detail="No suitable worker found")
                )
                failed_instance_numbers.append(instance_number)

        if failed_instance_numbers:
            job_operations.update_job(
                job_id,
                {
                    "status": DeploymentStatus.FAILED.value,
                    "status_detail": "Failed instance(s): "
                                     + ", ".join(str(x) for x in failed_instance_numbers),
                },
            )

    return


def aggregate_info(time_interval_seconds: int) -> List[AnyJob]:
    mark_inactive_as_failed(time_interval_seconds)
    jobs = job_operations.get_jobs() or []

    return [
        {
            "_id": job.get("_id"),
            "job_name": job.get("job_name"),
            "status": job.get("status", int(LegacyStatus.LEGACY_1.value)),
            "instance_list": job.get("instance_list"),
        }
        for job in jobs
    ]


def create_new_job_instance(job: Job, instance_number: int) -> Job:
    job_id = job.id

    updated_job_obj: Any
    if job_id is None or job_operations.get_job_by_id(job_id) is None:
        updated_job_obj = job_operations.create_job(job.model_dump(by_alias=True))
    else:
        updated_job_obj = job_operations.append_job_instance(job_id, instance_number, job.model_dump(by_alias=True))
    logger.debug(f"Created new job instance: {updated_job_obj}")

    updated_job = Job.model_validate(updated_job_obj)
    return updated_job


def update_deployed_instance_worker(
        job_name: Optional[str],
        instance_number: int,
        status: Optional[str],
        status_detail: Optional[str],
        public_ip: Optional[str]
) -> None:
    job_objs: List[Any] = job_operations.get_jobs(job_name=job_name)
    if not job_objs:
        return

    first_job = Job.model_validate(job_objs[0])

    job_id = first_job.require_id()

    update_status(job_id, instance_number, status, status_detail)
    update_instance(job_id, instance_number, JobInstance(publicip=public_ip))


def update_status(
        job_id: str,
        instance_number: int,
        status: Optional[str],
        status_detail: Optional[str] = None
) -> None:
    if status == DeploymentStatus.CREATED.value:
        return

    job_obj: Any = job_operations.get_job_by_id(job_id)
    if job_obj is None:
        return

    job = Job.model_validate(job_obj)
    instances = job.instance_list if job.instance_list is not None else []

    for instance in instances:
        if instance.instance_number == instance_number:
            instance.status = status
            if status_detail is not None:
                instance.status_detail = status_detail

    # Update job-level status, but only set RUNNING once all instances are running
    if status != DeploymentStatus.RUNNING.value:
        job.status = status
    elif all(instance.status == DeploymentStatus.RUNNING.value for instance in instances):
        job.status = status

    job_operations.update_job(job_id, job.model_dump(by_alias=True))


def update_instance_resources(
        job_name: Optional[str],
        instance_number: int,
        resources: JobInstanceResources
) -> bool:
    job_objs = job_operations.get_jobs(job_name=job_name)
    if not job_objs:
        return False

    first_job: Job = Job.model_validate(job_objs[0])
    job_id = first_job.require_id()

    update_status(
        job_id,
        instance_number,
        DeploymentStatus.RUNNING.value,
        None,  # I don't believe resources every carry a status detail
    )
    return update_instance(job_id, instance_number, JobInstance(
        cpu_percent=resources.cpu_percent,
        memory_percent=resources.memory_percent,
        disk=resources.disk,
        logs=resources.logs
    ))


def update_instance_node(job_id: str, instance_number: int, worker_id: str) -> bool:
    node: Any = candidate_operations.get_candidate_by_id(worker_id)
    if not isinstance(node, dict):
        return False

    # TODO: Find out what the type of the "port" value actually is to simplify handling
    host_port: int
    if not node.get("port"):
        host_port = 50011
    else:
        node_host_port = node["port"]
        if isinstance(node_host_port, int):
            host_port = node_host_port
        elif isinstance(node_host_port, float):
            host_port = round(node_host_port)
        elif isinstance(node_host_port, str):
            try:
                host_port = int(node_host_port)
            except ValueError:
                raise RuntimeError("Invalid 'port' in resource")
        else:
            raise RuntimeError("Invalid 'port' in resource")

    data = JobInstance(
        host_ip=node.get("ip"),
        host_port=host_port,
        worker_id=worker_id,
    )
    return update_instance(job_id, instance_number, data)


def update_instance(job_id: str, instance_number: int, instance: JobInstance) -> bool:
    job_obj = job_operations.get_job_by_id(job_id)
    if job_obj is None:
        return False
    job: Job = Job.model_validate(job_obj)

    instance.last_modified_timestamp = datetime.now(timezone.utc).timestamp()

    updated_instance: JobInstance
    if job.instance_list is None:
        instance.instance_number = instance_number
        job.instance_list = [instance]
        updated_instance = instance
    else:
        for existing_instance in job.instance_list:
            if existing_instance.instance_number == instance_number:
                existing_instance.update(instance)
                updated_instance = existing_instance
                break
        else:
            instance.instance_number = instance_number
            job.instance_list.append(instance)
            updated_instance = instance

    # TODO: do we need to coerce None/null values to an empty string?
    job_operations.update_job_instance(job_id, instance_number, updated_instance.model_dump(by_alias=True))
    return True


def deploy_job(job: Job, instance_number: int) -> None:
    updated_job: Job = create_new_job_instance(job, instance_number)
    scheduler_request_deploy(updated_job, instance_number)


def get_jobs_with_failed_instances() -> List[Job]:
    query = {
        "$or": [
            {"instance_list.status": DeploymentStatus.FAILED.value},
            {"instance_list.status": DeploymentStatus.DEAD.value},
            {"instance_list.status": NegativeSchedulingStatus.NO_WORKER_CAPACITY.value},
        ]
    }
    job_objs = job_operations.get_jobs(**query)
    if job_objs is None:
        return []

    return [Job.model_validate(job_obj) for job_obj in job_objs]


def delete_job_instance(
        job_id: str,
        instance_number: int,
        erase: bool = True
) -> None:
    # send instance undeployment to node
    job_obj = job_operations.get_job_by_id(job_id)
    if job_obj is None:
        return

    job: Job = Job.model_validate(job_obj)

    instance_list = job.instance_list
    if instance_list is None:
        return

    deleted_job_count = 0
    for instance in instance_list:
        if instance.instance_number == instance_number or instance_number == -1:
            logger.info(f"Deleting instance {instance.instance_number} of job {job_id}")
            deleted_job_count += 1
            worker_id = instance.worker_id

            if worker_id is not None:
                from clients.mqtt_client import mqtt_publish_edge_delete
                mqtt_publish_edge_delete(
                    worker_id,
                    job.require_job_name(),
                    instance.instance_number,
                    job.virtualization if job.virtualization is not None else "docker",
                )

            # remove from db if erase is true
            if erase:
                job_operations.delete_job_instance(job_id, instance.instance_number)
                logger.info(f"Deleted instance {instance.instance_number} of job {job_id} from DB")

    if erase and len(instance_list) <= deleted_job_count:
        job_operations.delete_job(job_id)
        logger.info(f"Deleted job {job_id} from DB as all instances were removed")
