from scripts.validate_exports import load_schema, validate_data


def test_load_schema_resolves_domains_without_network():
    validator = load_schema()
    payload = {
        "_schema": "device-knowledge/2.0",
        "mpn": "TEST-DEVICE",
        "domains": {
            "design_guide": {
                "source_document": {
                    "title": "Guide",
                }
            }
        },
    }

    assert validate_data(validator, payload) == []
