import json
import hashlib
import jsonschema

workflow_schema = {
    "$id": "http://odahub.io/ontology#workflow-schema",
    "properties": {
        "test": {
            "required": ["call_type", "call_context", "workflow"]
        }
    },
    "required": ["base", "inputs"]
}


def validate_workflow(w):
    jsonschema.validate(w, workflow_schema)


def w2uri(w, prefix="data"):
    validate_workflow(w)
    return f"data:{prefix}-{hashlib.sha256(json.dumps(w, sort_keys=True).encode()).hexdigest()[:16]}"
