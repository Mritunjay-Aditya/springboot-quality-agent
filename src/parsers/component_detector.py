from enum import Enum

from .java_ast_parser import JavaClass


class ComponentType(str, Enum):
    SERVICE = "service"
    CONTROLLER = "controller"
    REPOSITORY = "repository"
    UNKNOWN = "unknown"


def detect_component(java_class: JavaClass) -> ComponentType:
    annotations = {annotation.split(".")[-1] for annotation in java_class.annotations}
    if "RestController" in annotations or "Controller" in annotations:
        return ComponentType.CONTROLLER
    if "Service" in annotations:
        return ComponentType.SERVICE
    if "Repository" in annotations:
        return ComponentType.REPOSITORY
    return ComponentType.UNKNOWN
