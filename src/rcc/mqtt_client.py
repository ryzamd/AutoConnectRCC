import json
import re
import time
import logging
from typing import List, Dict
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# ── Shared Shelly Topic Patterns ──────────────────────────────
# Gen1 devices publish to: shellies/<model>-<mac>/<subtopic>
# Gen2 devices publish to: <model>-<mac>/<subtopic>
#   e.g. shellyplus1-aabbcc112233/status/switch:0
#        shellypro2pm-001122334455/events/rpc
#
# IMPORTANT: keep SHELLY_GEN2_PATTERN identical to rcc-engine's
# SHELLY_STATUS_PATTERN so that device IDs are constructed the same way
# in both programs: "<model>-<mac_lowercase>"
SHELLY_GEN2_PATTERN = re.compile(
    r"^(shelly[\w]+)-([0-9A-Fa-f]+)/(.+)$"
)
SHELLY_GEN1_PATTERN = re.compile(
    r"^shellies/(shelly[\w]+-[0-9A-Fa-f]+)/(.+)$"
)


class MQTTVerifier:
    def __init__(self, broker_ip: str, port: int = 1883,
                 username: str = "", password: str = ""):
        self.broker_ip = broker_ip
        self.port = port
        self.username = username
        self.password = password
        self.found_devices: List[Dict] = []
        self._connected = False

        client_id = f"rcc-verifier-{int(time.time())}"
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)

        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            logger.info("Connected to MQTT broker")

            # Gen2 devices: publish directly as <model>-<mac>/...
            # Same wildcard 'shelly#' as rcc-engine's mqtt_mediator — must stay in sync.
            client.subscribe("shelly#", 0)

            # Gen1 devices (legacy): publish under shellies/<model>-<mac>/...
            client.subscribe("shellies/#", 0)

            # Supplementary Gen2 discovery topics
            client.subscribe("+/online", 0)
            client.subscribe("+/announce", 0)
            client.subscribe("+/events/rpc", 0)
            client.subscribe("+/status/wifi", 0)
            # Response topic for our outgoing WiFi.GetStatus RPC calls
            client.subscribe("rcc-verifier/rpc", 0)

            # Trigger Gen1 device announcements
            client.publish("shellies/command", "announce")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            topic = msg.topic

            logger.debug(f"Received message on {topic}: {payload}")

            # ── Gen2: <model>-<mac>/<subtopic> ───────────────────────────
            gen2_match = SHELLY_GEN2_PATTERN.match(topic)
            if gen2_match:
                model     = gen2_match.group(1)
                mac       = gen2_match.group(2).upper()
                sub_topic = gen2_match.group(3)
                device_id = f"{model}-{mac.lower()}"

                self._add_device({
                    "id": device_id, "model": model,
                    "mac": mac, "ip": "Check DHCP",
                    "gen": 2, "status": "online",
                })

                # Extract IP from wifi status sub-topic
                if sub_topic == "status/wifi":
                    try:
                        data = json.loads(payload)
                        ip = data.get("sta_ip")
                        if ip:
                            self._update_device_ip(device_id, ip)
                    except json.JSONDecodeError:
                        pass
                return

            # ── Gen1: shellies/<model>-<mac>/<subtopic> ──────────────────
            gen1_match = SHELLY_GEN1_PATTERN.match(topic)
            if gen1_match:
                device_id = gen1_match.group(1)
                model     = device_id.rsplit("-", 1)[0]
                self._add_device({
                    "id": device_id, "model": model,
                    "mac": "Unknown", "ip": "Check DHCP",
                    "gen": 1, "status": "online",
                })
                return

            # ── Supplementary discovery topics ────────────────────────────
            if topic.endswith("/announce"):
                try:
                    data = json.loads(payload)
                    device_name = data.get("name") or data.get("id")
                    normalized = {
                        "id":          device_name,
                        "original_id": data.get("id"),
                        "mac":         data.get("mac", "Unknown"),
                        "model":       data.get("model") or data.get("app", "Unknown"),
                        "ip":          data.get("ip", "Unknown"),
                        "gen":         data.get("gen", 1),
                    }
                    self._add_device(normalized)

                    # For Gen2, request IP via RPC
                    if data.get("gen", 1) >= 2 and device_name:
                        rpc_request = json.dumps({
                            "id":     int(time.time()),
                            "src":    "rcc-verifier",
                            "method": "WiFi.GetStatus",
                        })
                        client.publish(f"{device_name}/rpc", rpc_request)
                except json.JSONDecodeError:
                    pass

            elif topic.endswith("/online"):
                prefix = topic.split("/")[0]
                self._add_device({
                    "id": prefix, "ip": "Check DHCP",
                    "model": "Device", "mac": "Unknown",
                    "status": payload,
                })

            elif topic.endswith("/events/rpc"):
                prefix = topic.split("/")[0]
                try:
                    data = json.loads(payload)
                    src = data.get("src", "")
                    mac = "Unknown"
                    if "-" in src:
                        parts = src.split("-")
                        if len(parts) >= 2:
                            possible_mac = parts[-1].upper()
                            if len(possible_mac) == 12:
                                mac = possible_mac

                    self._add_device({
                        "id": prefix, "ip": "Check DHCP",
                        "model": "Gen2 Device", "mac": mac,
                        "status": "online (rpc)",
                    })
                except json.JSONDecodeError:
                    pass

            elif topic.endswith("/status/wifi"):
                prefix = topic.split("/")[0]
                try:
                    data = json.loads(payload)
                    ip = data.get("sta_ip")
                    if ip:
                        self._update_device_ip(prefix, ip)
                except json.JSONDecodeError:
                    pass

            elif topic == "rcc-verifier/rpc":
                try:
                    data = json.loads(payload)
                    result = data.get("result", {})
                    ip  = result.get("sta_ip")
                    src = data.get("src", "")

                    logger.debug(f"RPC response: src={src}, ip={ip}, devices={len(self.found_devices)}")

                    if ip and src:
                        src_mac = ""
                        if "-" in src:
                            parts = src.split("-")
                            if len(parts) >= 2:
                                possible_mac = parts[-1].upper()
                                if len(possible_mac) == 12:
                                    src_mac = possible_mac

                        for device in self.found_devices:
                            device_mac  = device.get("mac", "").upper()
                            original_id = device.get("original_id", "")
                            device_id   = device.get("id", "")

                            if (src_mac and device_mac == src_mac) \
                                    or original_id == src or device_id == src:
                                device["ip"] = ip
                                logger.info(f"Updated IP {ip} for device {device_id}")
                                break
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _update_device_ip(self, device_id: str, ip: str) -> None:
        """Update the IP address of a known device by id."""
        for device in self.found_devices:
            if device.get("id") == device_id:
                device["ip"] = ip
                logger.info(f"Updated IP {ip} for device {device_id}")
                return

    def _add_device(self, data: Dict):
        device_id = data.get("id")
        if not device_id:
            return

        new_mac = data.get("mac")

        for device in self.found_devices:
            existing_mac = device.get("mac")
            existing_id  = device.get("id")

            mac_match = (new_mac and existing_mac and
                         new_mac != "Unknown" and existing_mac != "Unknown" and
                         new_mac == existing_mac)
            id_match = (device_id == existing_id)

            if mac_match or id_match:
                # Prefer descriptive name over placeholder
                if not device_id.startswith("RCC-Device"):
                    device["id"] = device_id

                if data.get("ip") and data.get("ip") != "Check DHCP":
                    device["ip"] = data["ip"]

                if data.get("model") and data.get("model") not in ("Device", "Gen2 Device"):
                    device["model"] = data["model"]

                if new_mac and new_mac != "Unknown":
                    device["mac"] = new_mac

                return

        self.found_devices.append(data)

    def verify(self, timeout: int = 5) -> List[Dict]:
        try:
            logger.info(f"Connecting to {self.broker_ip}:{self.port}...")
            self.client.connect(self.broker_ip, self.port, 60)
            self.client.loop_start()

            start_time = time.time()
            while not self._connected:
                if time.time() - start_time > 5:
                    logger.error("Connection timeout")
                    break
                time.sleep(0.1)

            if self._connected:
                logger.info(f"Listening for devices for {timeout} seconds...")
                time.sleep(timeout)

        except Exception as e:
            logger.error(f"MQTT Error: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

        return self.found_devices
