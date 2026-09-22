"""Generate JSON Schema for RiskInput.

Run: python -m schemas.generate_risk_input_schema
Output: schemas/risk-input-v1.schema.json
"""

import json
from pathlib import Path

from leo_risk.contracts.risk_input import RiskInput


def main() -> None:
    schema = RiskInput.model_json_schema()
    output = Path(__file__).parent / "risk-input-v1.schema.json"
    output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    print(f"Schema written to {output}")


if __name__ == "__main__":
    main()
