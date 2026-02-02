# services/arduino_communicator.py

import serial
import time
import threading
from queue import Queue, Empty
import logging
import sys
import os
from typing import Dict, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

logger = logging.getLogger(__name__)

class ArduinoCommunicator:
    def __init__(self, port: str, baud_rate: int, timeout: float = 1.0, name: str = "Arduino"):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.name = name
        self.serial_connection: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self._reader_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._message_queue: Queue = Queue()
        self._lock = threading.Lock()

    def connect(self) -> bool:
        if self.is_connected:
            logger.info(f"[{self.name}] Already connected on {self.port}.")
            return True
        try:
            logger.info(f"[{self.name}] Attempting to connect on {self.port}...")
            self.serial_connection = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            time.sleep(config.SERIAL_CONNECT_TIMEOUT_S)
            
            if self.serial_connection.in_waiting > 0:
                raw_message = self.serial_connection.read_until(b'>').decode('utf-8').strip()
                if "Ready" in raw_message:
                    self.is_connected = True
                    self._shutdown_event.clear()
                    self._reader_thread = threading.Thread(target=self._reader_thread_loop, daemon=True, name=f"{self.name}Reader")
                    self._reader_thread.start()
                    logger.info(f"[{self.name}] Connection successful. Received: {raw_message}")
                    return True
            
            logger.error(f"[{self.name}] No ready signal received from {self.port}.")
            if self.serial_connection: self.serial_connection.close()
            return False
        except serial.SerialException as e:
            logger.error(f"[{self.name}] Failed to connect on {self.port}: {e}")
            return False

    def disconnect(self):
        if not self.is_connected: return
        logger.info(f"[{self.name}] Disconnecting from {self.port}...")
        self._shutdown_event.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
        self.is_connected = False
        logger.info(f"[{self.name}] Disconnected.")

    def _reader_thread_loop(self):
        logger.info(f"[{self.name}] Reader thread started.")
        while not self._shutdown_event.is_set():
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    raw_message = self.serial_connection.read_until(b'>').decode('utf-8').strip()
                    if raw_message:
                        logger.debug(f"[{self.name}] Raw Rx: {raw_message}")
                        parsed = self._parse_message(raw_message)
                        if parsed: self._message_queue.put(parsed)
                else:
                    time.sleep(0.01)
            except (serial.SerialException, TypeError, UnicodeDecodeError) as e:
                logger.warning(f"[{self.name}] Error in reader thread: {e}")
                self.is_connected = False
                break
        logger.info(f"[{self.name}] Reader thread shutting down.")

    def _parse_message(self, message: str) -> Optional[Dict]:
        if not message.startswith('<') or not message.endswith('>'):
            return None
        content = message[1:-1]
        parts = content.split(':', 1)
        msg_type = parts[0]
        msg_payload_str = parts[1] if len(parts) > 1 else ""
        
        payload = {}
        if msg_type == "DATA" and msg_payload_str.startswith("SENSORS:"):
            payload_str = msg_payload_str.replace("SENSORS:", "")
            try:
                for item in payload_str.split(','):
                    key, value_str = item.split(':')
                    try:
                        payload[key] = float(value_str) if '.' in value_str else int(value_str)
                    except ValueError:
                        payload[key] = 0
            except (ValueError, IndexError):
                return None
        
        return {"type": msg_type, "payload_str": msg_payload_str, "payload": payload}

    def send_command(self, command: str, expect_ack: bool = True, timeout: float = 2.0) -> bool:
        if not self.is_connected or not self.serial_connection: return False
        full_command = f"<{command}>"
        with self._lock:
            try:
                self.serial_connection.write(full_command.encode('utf-8'))
                logger.debug(f"[{self.name}] Tx: {command}")
                if not expect_ack: return True
                
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        msg = self._message_queue.get(timeout=0.1)
                        if msg.get('type') == 'ACK':
                            return True
                    except Empty:
                        continue
                logger.warning(f"[{self.name}] Timeout waiting for ACK for command: {command}")
                return False
            except serial.SerialException as e:
                logger.error(f"[{self.name}] Serial error sending '{command}': {e}")
                self.disconnect()
                return False

    # --- FIX IS HERE ---
    def get_sensors(self, timeout: float = 0.5) -> Optional[Dict]:
        if not self.is_connected or not self.serial_connection: return None
        with self._lock:
            while not self._message_queue.empty():
                try: self._message_queue.get_nowait()
                except Empty: break
            
            try:
                self.serial_connection.write(b'<get_data>')
                logger.debug(f"[{self.name}] Tx: get_data")
            except serial.SerialException as e:
                logger.error(f"[{self.name}] Serial error during get_sensors write: {e}")
                self.disconnect()
                return None

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    msg = self._message_queue.get(timeout=0.1)
                    if msg.get('type') == 'DATA' and msg.get('payload_str', '').startswith('SENSORS:'):
                        return msg['payload']
                    else:
                        continue
                except Empty:
                    continue
        logger.warning(f"[{self.name}] Timeout waiting for SENSOR data response.")
        return None
    
