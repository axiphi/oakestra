import json
import logging
import re
from typing import Any, Optional, Dict

import paho.mqtt.client as paho_mqtt
from paho.mqtt.client import MQTTMessage
from resource_abstractor_client import candidate_operations
from typing_extensions import assert_type

from clients.job_management import update_instance_resources, update_deployed_instance_worker
from config import CONFIG
from oakestra_utils.types.statuses import convert_to_status
from models.job import Job, JobInstanceResources

logger = logging.getLogger("cluster_manager")

_mqtt: Optional[paho_mqtt.Client] = None

def ensure_mqtt() -> paho_mqtt.Client:
    global _mqtt
    if not _mqtt:
        raise RuntimeError("Expected MQTT to be initialized")
    return _mqtt


def handle_connect(_client: Any, _userdata: Any, _flags: Any, _rc: Any) -> None:
    mqtt = ensure_mqtt()

    logger.info("MQTT - Connected to MQTT Broker")
    mqtt.subscribe("nodes/+/information")
    mqtt.subscribe("nodes/+/job")
    mqtt.subscribe("nodes/+/jobs/resources")


def handle_logging(_client: Any, _userdata: Any, level: str, buf: Any) -> None:
    if level == "MQTT_LOG_ERR":
        logger.info("Error: {}".format(buf))


# TODO: add type validation for all message types
def handle_mqtt_message(_client: Any, _userdata: Any, message: MQTTMessage):
    payload_bytes: bytes = assert_type(message.payload, bytes)

    topic = message.topic
    payload_str = payload_bytes.decode()
    logger.info("MQTT - Received from worker - %s: %s", topic, payload_str)

    re_nodes_information_topic = re.search("^nodes/.*/information$", topic)
    re_job_deployment_topic = re.search("^nodes/.*/job$", topic)
    re_job_resources_topic = re.search("^nodes/.*/jobs/resources$", topic)

    topic_split = topic.split("/")
    client_id = topic_split[1]
    payload = json.loads(payload_str)

    # if topic starts with nodes and ends with information
    if re_nodes_information_topic is not None:
        mqtt = ensure_mqtt()

        nonnull_payload = {k: v for k, v in payload.items() if v is not None}
        updated = candidate_operations.update_candidate_information(client_id, nonnull_payload)
        if updated is None:
            mqtt.publish(
                "nodes/" + client_id + "/control/error",
                json.dumps({"message": "Node not registered to the cluster"}),
            )

    if re_job_deployment_topic is not None:
        job_name = payload.get("sname")
        status = convert_to_status(payload.get("status"))
        status_detail = payload.get("status_detail", None)
        instance = int(payload.get("instance"))
        publicip = payload.get("publicip", "--")
        update_deployed_instance_worker(job_name, instance, status.value, status_detail, publicip)


    if re_job_resources_topic is not None:
        services = payload.get("services")
        for instance_resources_obj in services:
            instance_resources = JobInstanceResources.model_validate(instance_resources_obj)

            try:
                # If unable to update then worker has outdated information
                # and service must be undeployed
                if (
                    not update_instance_resources(
                        instance_resources.job_name,
                        instance_resources.require_instance(),
                        instance_resources
                    )
                ):
                    mqtt_publish_edge_delete(
                        client_id,
                        instance_resources.require_job_name(),
                        instance_resources.require_instance(),
                        instance_resources.virtualization
                    )
            except Exception as e:
                logger.error("MQTT - unable to update service resources")
                logger.error(e)


def initialize_mqtt():
    mqtt = paho_mqtt.Client()

    global _mqtt
    _mqtt = mqtt


    mqtt.on_connect = handle_connect
    mqtt.on_message = handle_mqtt_message
    mqtt.reconnect_delay_set(min_delay=1, max_delay=120)
    mqtt.max_queued_messages_set(1000)
    if CONFIG.mqtt_cert:
        try:
            mqtt.tls_set(
                ca_certs=CONFIG.mqtt_cert + "/ca.crt",
                certfile=CONFIG.mqtt_cert + "/cluster.crt",
                keyfile=CONFIG.mqtt_cert + "/cluster.key",
                keyfile_password=CONFIG.cluster_keyfile_password,
            )
            logger.info("MQTT - TLS configured")
        except FileNotFoundError as e:
            logger.error("MQTT - Unable to load certificate files")
            logger.error(e)

    mqtt.connect(
        CONFIG.mqtt_broker_url.strip("[]"),
        CONFIG.mqtt_broker_port,
        keepalive=5,
    )
    mqtt.loop_start()


def mqtt_publish_edge_deploy(
        worker_id: str,
        job: Job,
        instance_number: int
):
    topic = "nodes/" + worker_id + "/control/deploy"

    data: Dict[str, Any] = job.model_dump(by_alias=True)
    data["instance_number"] = instance_number

    mqtt = ensure_mqtt()
    mqtt.publish(topic, json.dumps(data))  # MQTT cannot send JSON, dump it to String here


def mqtt_publish_edge_delete(
        worker_id: str,
        job_name: str,
        instance_number: int,
        runtime: Optional[str]="docker"
):
    topic = "nodes/" + worker_id + "/control/delete"

    data: Dict[str, Any] = {
        "job_name": job_name,
        "virtualization": runtime,
        "instance_number": instance_number,
    }

    mqtt = ensure_mqtt()
    mqtt.publish(topic, json.dumps(data))
