import json
import time
import logging
import socket
from typing import List, Dict, Optional
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class MQTTVerifier:
    def __init__(self, broker_ip: str, port: int = 1883, username: str = "", password: str = ""):
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
            client.subscribe("shellies/#")
            client.subscribe("+/online")
            client.subscribe("+/announce")
            client.subscribe("+/events/rpc")
            client.publish("shellies/command", "announce")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            topic = msg.topic
            
            logger.debug(f"Received message on {topic}: {payload}")
            
            if topic.endswith("/announce"):
                try:
                    data = json.loads(payload)
                    self._add_device(data)
                except json.JSONDecodeError:
                    pass
            
            elif topic.endswith("/online"):
                prefix = topic.split("/")[0]
                status = payload
                self._add_device({
                    "id": prefix,
                    "ip": "Check DHCP", 
                    "model": "Device", 
                    "mac": "Unknown",
                    "status": status
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
                        "id": prefix,
                        "ip": "Check DHCP", 
                        "model": "Gen2 Device", 
                        "mac": mac,
                        "status": "online (rpc)"
                    })
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _add_device(self, data: Dict):
        device_id = data.get("id")
        if not device_id:
            return
            
        new_mac = data.get("mac")
        
        for i, device in enumerate(self.found_devices):
            existing_mac = device.get("mac")
            existing_id = device.get("id")
            
            mac_match = (new_mac and existing_mac and 
                         new_mac != "Unknown" and existing_mac != "Unknown" and 
                         new_mac == existing_mac)
            
            id_match = (device_id == existing_id)
            
            if mac_match or id_match:
                if device_id.startswith("RCC-Device"):
                    device["id"] = device_id
                elif existing_id.startswith("RCC-Device"):
                    pass
                
                if data.get("ip") and data.get("ip") != "Check DHCP":
                    device["ip"] = data.get("ip")
                
                if data.get("model") and data.get("model") != "Device":
                    device["model"] = data.get("model")
                    
                if new_mac != "Unknown":
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
