"""
test_booking_notification_email.py — tests for the owner-notification email
sent after a successful /book call (see routes/dispatch.py: notify_owner).

The SMTP layer (smtplib.SMTP_SSL) is always mocked here — no real email is
ever sent and no real credentials are needed to run this suite.
_run_in_background is patched to run its function immediately instead of on
a background thread, so the (mocked) send completes before each test
asserts on it.
"""

from unittest.mock import patch

import routes.dispatch as dispatch
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


def _run_immediately(fn):
    fn()


@patch("routes.dispatch._run_in_background", side_effect=_run_immediately)
@patch("routes.dispatch.smtplib.SMTP_SSL")
class TestBookingNotificationEmail:
    """These patch the env-backed module globals directly via monkeypatch,
    which is equivalent to setting OWNER_NOTIFY_EMAIL/SMTP_USER/SMTP_PASSWORD
    and re-importing, without needing real env vars or credentials."""

    def _configure_env(self, monkeypatch):
        monkeypatch.setattr(dispatch, "OWNER_NOTIFY_EMAIL", "owner@example.com")
        monkeypatch.setattr(dispatch, "SMTP_USER", "allrhodesmedia@gmail.com")
        monkeypatch.setattr(dispatch, "SMTP_PASSWORD", "app-password")

    def test_email_sent_on_successful_booking(
        self, mock_smtp_ssl, mock_run_bg, client, mock_save_booking, monkeypatch
    ):
        self._configure_env(monkeypatch)
        smtp_instance = mock_smtp_ssl.return_value.__enter__.return_value

        response = post_booking(client, VALID_PAYLOAD)

        assert response.status_code == 200
        smtp_instance.login.assert_called_once_with(
            "allrhodesmedia@gmail.com", "app-password"
        )
        smtp_instance.send_message.assert_called_once()

        sent_message = smtp_instance.send_message.call_args[0][0]
        assert sent_message["To"] == "owner@example.com"
        assert sent_message["From"] == "allrhodesmedia@gmail.com"
        body = sent_message.get_content()
        assert "Jane Doe" in body
        assert "123 Main St, Austin, TX 78701" in body
        assert "AC repair" in body
        assert "999" in body  # booking_id returned by the mocked save_booking

    def test_emergency_subject_prefix(
        self, mock_smtp_ssl, mock_run_bg, client, mock_save_booking, monkeypatch
    ):
        self._configure_env(monkeypatch)
        smtp_instance = mock_smtp_ssl.return_value.__enter__.return_value

        payload = {**VALID_PAYLOAD, "is_emergency": "true"}
        response = post_booking(client, payload)

        assert response.status_code == 200
        sent_message = smtp_instance.send_message.call_args[0][0]
        assert sent_message["Subject"].startswith("EMERGENCY")

    def test_non_emergency_subject_has_no_prefix(
        self, mock_smtp_ssl, mock_run_bg, client, mock_save_booking, monkeypatch
    ):
        self._configure_env(monkeypatch)
        smtp_instance = mock_smtp_ssl.return_value.__enter__.return_value

        response = post_booking(client, VALID_PAYLOAD)

        assert response.status_code == 200
        sent_message = smtp_instance.send_message.call_args[0][0]
        assert not sent_message["Subject"].startswith("EMERGENCY")

    def test_no_email_when_booking_fails_validation(
        self, mock_smtp_ssl, mock_run_bg, client, mock_save_booking, monkeypatch
    ):
        self._configure_env(monkeypatch)

        payload = {**VALID_PAYLOAD, "customer_name": "UNKNOWN"}
        response = post_booking(client, payload)

        assert response.status_code == 400
        mock_save_booking.assert_not_called()
        mock_run_bg.assert_not_called()
        mock_smtp_ssl.assert_not_called()

    def test_booking_still_succeeds_when_email_send_raises(
        self, mock_smtp_ssl, mock_run_bg, client, mock_save_booking, monkeypatch
    ):
        self._configure_env(monkeypatch)
        mock_smtp_ssl.side_effect = Exception("SMTP connection refused")

        response = post_booking(client, VALID_PAYLOAD)

        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "booked"
        assert body["booking_id"] == 999


class TestMissingEnvVarsSkipsEmailSend:
    def test_no_smtp_attempt_when_credentials_not_configured(
        self, client, mock_save_booking
    ):
        # The default test environment (tests/conftest.py) never sets
        # OWNER_NOTIFY_EMAIL, SMTP_USER, or SMTP_PASSWORD, so notify_owner
        # should log a warning and return without touching smtplib at all.
        with patch("routes.dispatch.smtplib.SMTP_SSL") as mock_smtp_ssl:
            response = post_booking(client, VALID_PAYLOAD)

        assert response.status_code == 200
        mock_smtp_ssl.assert_not_called()
