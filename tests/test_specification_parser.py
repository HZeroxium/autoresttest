from __future__ import annotations

from autoresttest.specification.specification_parser import SpecificationParser


def test_process_responses_normalizes_integer_status_codes() -> None:
    parser = SpecificationParser.__new__(SpecificationParser)

    responses = {
        200: {
            "description": "OK",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                        },
                    }
                }
            },
        },
        404: {
            "description": "Not Found",
        },
    }

    processed = parser.process_responses(responses)

    assert set(processed) == {"200", "404"}
    assert processed["200"].status_code == "200"
    assert processed["404"].status_code == "404"
    assert "application/json" in processed["200"].content
