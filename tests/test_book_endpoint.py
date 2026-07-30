"""
test_book_endpoint.py — tests for POST /book.

The placeholder-value tests below are a direct regression test for a real
incident (2026-07-30): a live phone call had the model satisfy Retell's
"required" function-schema constraint by sending the literal string
"UNKNOWN" for customer_name/service_address instead of actually asking the
caller. This suite exists so that exact bug class can never silently
reappear without a test immediately failing.
"""

import pytest

from conftest import API_KEY

VALID_PAYLOAD = {
    "job_type": "AC repair",
    "urgency": "high",
    "is_emergency": "false",
    "summary": "Test booking",
    "suggested_action": "Dispatch technician",
    "customer_name": "Jane Doe",
    "service_address": "123 Main St, Austin, TX 78701",
    "business_name": "Test HVAC Co",
}


def post_booking(client, payload, api_key=API_KEY):
    headers = {}
    if api_key is not None:
        headers["X-API-Key"] = api_key
    return client.post("/book", json=payload, headers=headers)


class TestAuth:
    def test_missing_api_key_rejected(self, client, mock_save_booking):
        response = post_booking(client, VALID_PAYLOAD, api_key=None)
        assert response.status_code == 401

    def test_wrong_api_key_rejected(self, client, mock_save_booking):
        response = post_booking(client, VALID_PAYLOAD, api_key="wrong-key")
        assert response.status_code == 401

    def test_correct_api_key_accepted(self, client, mock_save_booking):
        response = post_booking(client, VALID_PAYLOAD)
        assert response.status_code == 200


class TestValidPayload:
    def test_complete_valid_payload_succeeds(self, client, mock_save_booking):
        response = post_booking(client, VALID_PAYLOAD)
        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "booked"
        assert body["booking_id"] == 999
        mock_save_booking.assert_called_once()

    def test_real_data_passed_through_unchanged(self, client, mock_save_booking):
        post_booking(client, VALID_PAYLOAD)
        called_with = mock_save_booking.call_args[0][0]
        assert called_with["customer_name"] == "Jane Doe"
        assert called_with["service_address"] == "123 Main St, Austin, TX 78701"


class TestMissingFields:
    @pytest.mark.parametrize("missing_field", [
        "job_type", "urgency", "is_emergency", "summary",
        "suggested_action", "customer_name", "service_address", "business_name",
    ])
    def test_missing_key_rejected(self, client, mock_save_booking, missing_field):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != missing_field}
        response = post_booking(client, payload)
        assert response.status_code == 400
        assert missing_field in response.get_json()["error"]
        mock_save_booking.assert_not_called()


class TestBlankValues:
    @pytest.mark.parametrize("blank_value", ["", "   ", "\t", "\n"])
    def test_blank_value_rejected(self, client, mock_save_booking, blank_value):
        payload = {**VALID_PAYLOAD, "customer_name": blank_value}
        response = post_booking(client, payload)
        assert response.status_code == 400
        assert "customer_name" in response.get_json()["error"]
        mock_save_booking.assert_not_called()


class TestPlaceholderValues:
    """
    Regression coverage for the real 2026-07-30 incident: 'required' in
    Retell's schema forces a field to be present, not truthful. The model
    sent literal placeholder strings to satisfy the schema instead of
    asking the caller for real information.
    """

    @pytest.mark.parametrize("placeholder", [
        "UNKNOWN", "unknown", "Unknown",
        "N/A", "n/a",
        "TBD", "tbd",
        "None", "none",
        "null",
        "pending",
        "Not Provided", "not provided",
        "Not Available", "not available",
    ])
    def test_placeholder_value_rejected(self, client, mock_save_booking, placeholder):
        payload = {**VALID_PAYLOAD, "customer_name": placeholder}
        response = post_booking(client, payload)
        assert response.status_code == 400, (
            f"'{placeholder}' should have been rejected as a placeholder value "
            f"but was accepted — this is the exact bug that shipped a real "
            f"junk booking (id 7) on 2026-07-30."
        )
        assert "customer_name" in response.get_json()["error"]
        mock_save_booking.assert_not_called()

    def test_placeholder_in_service_address_also_rejected(self, client, mock_save_booking):
        payload = {**VALID_PAYLOAD, "service_address": "UNKNOWN"}
        response = post_booking(client, payload)
        assert response.status_code == 400
        assert "service_address" in response.get_json()["error"]
