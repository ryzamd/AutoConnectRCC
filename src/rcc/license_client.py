"""
RCC License Admin MQTT Client
Publishes license admin commands (activate, migrate) to the Pi's Watcher
and waits for the response via MQTT.

Separate from MQTTVerifier (one-shot device scan) — this client handles
persistent request/response patterns with timeouts.
"""

import json
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    logger.warning("paho-mqtt not available — license admin client disabled")


class LicenseAdminClient:
    """
    Short-lived MQTT client for license admin operations.
    Usage:
        client = LicenseAdminClient(host, port, username, password)
        result = client.activate("RCC-2026-ABC")
        result = client.migrate(transfer_token, password)
    """

    # ── MQTT Topics ────────────────────────────────────────────
    TOPIC_LICENSE_CMD    = "rcc/admin/v1/license"
    TOPIC_LICENSE_RESP   = "rcc/v1/license/response"
    TOPIC_MIGRATE_CMD    = "rcc/admin/v1/migrate"
    TOPIC_MIGRATE_RESP   = "rcc/v1/migrate/response"
    TOPIC_STATUS_LICENSE = "rcc/v1/status/license"

    _RC_ERRORS = {
        1: "Incorrect protocol version",
        2: "Invalid client identifier",
        3: "Server unavailable",
        4: "Bad username or password",
        5: "Not authorized",
    }

    def __init__(self, host: str, port: int = 1883,
                 username: str = "", password: str = ""):
        self._host = host
        self._port = port
        self._username = username
        self._password = password

        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._connect_error: Optional[str] = None
        self._response: Optional[dict] = None
        self._response_event = threading.Event()

    # ── Public API ─────────────────────────────────────────────

    def activate(self, license_key: str, timeout: float = 15.0) -> dict:
        """
        Send activation request to Watcher and wait for response.

        Args:
            license_key: the 25-character license key (RCCXX-XXXXX-XXXXX-XXXXX-XXXXX)
            timeout: seconds to wait for response

        Returns:
            {"success": True, "tier": ..., "max_devices": ..., "message": ...}
            or {"success": False, "error": "..."}
        """
        payload = {
            "action": "activate",
            "license_key": license_key,
        }
        return self._request(
            cmd_topic=self.TOPIC_LICENSE_CMD,
            resp_topic=self.TOPIC_LICENSE_RESP,
            payload=payload,
            timeout=timeout,
        )

    def migrate(self, transfer_token: str, activation_password: str,
                timeout: float = 15.0) -> dict:
        """
        Send hardware migration request to Watcher and wait for response.

        Args:
            transfer_token: SHA-256 transfer token from decrypted license
            activation_password: the license activation password
            timeout: seconds to wait for response

        Returns:
            {"success": True, "tier": ..., "max_devices": ..., "message": ...}
            or {"success": False, "error": "..."}
        """
        payload = {
            "transfer_token": transfer_token,
            "password": activation_password,
        }
        return self._request(
            cmd_topic=self.TOPIC_MIGRATE_CMD,
            resp_topic=self.TOPIC_MIGRATE_RESP,
            payload=payload,
            timeout=timeout,
        )

    def get_license_status(self, timeout: float = 30.0) -> dict:
        """
        Wait for the next license status message from Watcher.

        Returns:
            {"needs_migration": bool, "needs_activation": bool, ...}
            or {"success": False, "error": "timeout"}
        """
        return self._listen(
            topic=self.TOPIC_STATUS_LICENSE,
            timeout=timeout,
        )

    # ── Internal ───────────────────────────────────────────────

    def _request(self, cmd_topic: str, resp_topic: str,
                 payload: dict, timeout: float) -> dict:
        """Connect → subscribe response → publish command → wait → disconnect."""
        if not HAS_MQTT:
            return {"success": False, "error": "paho-mqtt not installed"}

        self._response = None
        self._response_event.clear()

        try:
            self._connect(resp_topic)

            # Publish command
            msg = json.dumps(payload)
            result = self._client.publish(cmd_topic, msg, qos=1)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                return {"success": False,
                        "error": f"Failed to publish command (rc={result.rc})"}

            logger.info("Published to %s, waiting for response on %s (timeout=%ds)...",
                        cmd_topic, resp_topic, timeout)

            # Wait for response
            if self._response_event.wait(timeout=timeout):
                return self._response or {"success": False, "error": "Empty response"}
            else:
                return {"success": False,
                        "error": f"No response from Pi within {timeout}s — is Watcher running?"}

        except Exception as e:
            logger.error("License admin request failed: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            self._disconnect()

    def _listen(self, topic: str, timeout: float) -> dict:
        """Connect → subscribe → wait for first message → disconnect."""
        if not HAS_MQTT:
            return {"success": False, "error": "paho-mqtt not installed"}

        self._response = None
        self._response_event.clear()

        try:
            self._connect(topic)

            logger.info("Listening on %s (timeout=%ds)...", topic, timeout)

            if self._response_event.wait(timeout=timeout):
                return self._response or {"success": False, "error": "Empty response"}
            else:
                return {"success": False,
                        "error": f"No status received within {timeout}s"}

        except Exception as e:
            logger.error("License status listen failed: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            self._disconnect()

    def _connect(self, subscribe_topic: str) -> None:
        """Create client, connect, subscribe to response/status topic."""
        client_id = f"rcc-admin-{int(time.time())}"
        self._client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)

        if self._username and self._password:
            self._client.username_pw_set(self._username, self._password)

        self._client.on_connect = lambda c, u, f, rc: self._on_connect(c, rc, subscribe_topic)
        self._client.on_message = self._on_message

        self._connect_error = None
        self._client.connect(self._host, self._port, keepalive=30)
        self._client.loop_start()

        # Wait for connection
        deadline = time.time() + 5.0
        while not self._connected and time.time() < deadline:
            time.sleep(0.1)

        if not self._connected:
            err = self._connect_error or "connection timeout"
            raise ConnectionError(
                f"Could not connect to MQTT broker at {self._host}:{self._port} ({err})"
            )

    def _disconnect(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._connected = False

    def _on_connect(self, client, rc, subscribe_topic: str) -> None:
        if rc == 0:
            self._connected = True
            client.subscribe(subscribe_topic, qos=1)
            logger.info("Admin client connected, subscribed to %s", subscribe_topic)
        else:
            err_msg = self._RC_ERRORS.get(rc, f"Unknown error (rc={rc})")
            self._connect_error = err_msg
            logger.error("Admin client connection failed: %s", err_msg)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            logger.info("Response received on %s: %s", msg.topic, payload)
            self._response = payload
            self._response_event.set()
        except Exception as e:
            logger.error("Failed to parse response: %s", e)
            self._response = {"success": False, "error": f"Invalid response: {e}"}
            self._response_event.set()
