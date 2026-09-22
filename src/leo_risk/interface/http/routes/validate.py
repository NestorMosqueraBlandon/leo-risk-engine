"""Development-only endpoint for RiskInput validation.

This endpoint exists SOLELY for:
1. OpenAPI documentation of the RiskInput schema
2. Testing RiskInput validation without implementing inference

It does NOT perform any model inference. It only validates that the
input conforms to the RiskInput contract.

Marked as internal/development — should not be exposed in production.
"""

from fastapi import APIRouter

from leo_risk.contracts.risk_input import RiskInput

router = APIRouter(tags=["development"])


@router.post(
    "/internal/validate-risk-input",
    response_model=RiskInput,
    summary="[Development] Validate a RiskInput payload",
    description=(
        "Validates that a JSON payload conforms to the RiskInput contract. "
        "Returns the validated RiskInput or detailed validation errors. "
        "This endpoint does NOT perform inference. "
        "**Internal use only — not exposed in production.**"
    ),
)
def validate_risk_input(payload: RiskInput) -> RiskInput:
    """Validate and return the RiskInput if valid."""
    return payload
