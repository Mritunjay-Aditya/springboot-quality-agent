import xml.etree.ElementTree as ET
from pathlib import Path


def parse_report(path: Path) -> dict:
    if not path.is_file():
        return {"available": False, "error": f"JaCoCo report not found: {path}"}
    root = ET.parse(path).getroot()
    counters = {}
    for counter in root.findall("./counter"):
        counters[counter.attrib["type"].lower()] = {
            "missed": int(counter.attrib["missed"]),
            "covered": int(counter.attrib["covered"]),
            "percentage": _percentage(counter.attrib["missed"], counter.attrib["covered"]),
        }
    uncovered_methods = []
    for class_node in root.findall("./package/class"):
        class_name = class_node.attrib.get("name", "").split("/")[-1]
        for method in class_node.findall("./method"):
            counter = method.find("./counter[@type='METHOD']")
            if counter is not None and int(counter.attrib.get("covered", "0")) == 0:
                uncovered_methods.append(
                    {"class": class_name, "method": method.attrib.get("name", "")}
                )
    return {
        "available": True,
        "counters": counters,
        "uncovered_methods": uncovered_methods,
    }


def _percentage(missed: str, covered: str) -> float:
    total = int(missed) + int(covered)
    return round(int(covered) / total, 4) if total else 1.0
