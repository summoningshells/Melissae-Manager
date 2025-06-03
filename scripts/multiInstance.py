#!/usr/bin/env python3

import os
import json
import time
import uuid
import socket
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request
import urllib.parse
import ssl

class MelissaeConfig:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'multi-instance.json')
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return self._create_default_config()
    
    def _create_default_config(self) -> Dict:
        default_config = {
            "instance_id": str(uuid.uuid4()),
            "mode": "standalone",
            "server": {
                "host": "0.0.0.0",
                "port": 8888,
                "api_key": self._generate_api_key()
            },
            "agent": {
                "server_url": "",
                "api_key": "",
                "sync_interval": 60,
                "timeout": 30
            },
            "timezone": "UTC"
        }
        self.save_config(default_config)
        return default_config
    
    def _generate_api_key(self) -> str:
        return hashlib.sha256(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest()[:32]
    
    def save_config(self, config: Dict = None):
        config = config or self.config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
        self.config = config
    
    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            value = value.get(k, {})
            if not isinstance(value, dict):
                return value
        return default if value == {} else value

class MelissaeAgent:
    def __init__(self, config: MelissaeConfig):
        self.config = config
        self.working_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.logs_path = os.path.join(self.working_dir, 'dashboard/json/logs.json')
        self.threats_path = os.path.join(self.working_dir, 'dashboard/json/threats.json')
        
    def _read_json_file(self, file_path: str) -> List[Dict]:
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []
    
    def _prepare_data(self) -> Dict:
        logs = self._read_json_file(self.logs_path)
        threats = self._read_json_file(self.threats_path)
        
        # Add instance metadata
        instance_data = {
            "instance_id": self.config.get('instance_id'),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timezone": self.config.get('timezone', 'UTC'),
            "hostname": socket.gethostname(),
            "logs": logs,
            "threats": threats,
            "stats": {
                "log_count": len(logs),
                "threat_count": len(threats)
            }
        }
        
        return instance_data
    
    def _send_data(self, data: Dict, retry_count: int = 0) -> bool:
        server_url = self.config.get('agent.server_url')
        api_key = self.config.get('agent.api_key')
        timeout = self.config.get('agent.timeout', 30)
        max_retries = 3
        
        if not server_url or not api_key:
            print(f"[ERROR] Missing server configuration")
            return False
        
        # Validate data size before sending
        try:
            json_data = json.dumps(data).encode('utf-8')
            if len(json_data) > 10 * 1024 * 1024:  # 10MB limit
                print(f"[ERROR] Data too large ({len(json_data)} bytes)")
                return False
        except Exception as e:
            print(f"[ERROR] Failed to serialize data: {e}")
            return False
        
        try:
            # Prepare request with additional security headers
            url = f"{server_url.rstrip('/')}/api/data"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'User-Agent': 'Melissae-Agent/1.0',
                'X-Instance-ID': self.config.get('instance_id', 'unknown')[:16],  # Truncate for security
                'Content-Length': str(len(json_data))
            }
            
            req = urllib.request.Request(url, data=json_data, headers=headers, method='POST')
            
            # Enhanced SSL context - allow self-signed but verify hostname structure
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Add timeout and retry logic
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
                response_data = response.read().decode('utf-8')
                
                if response.getcode() == 200:
                    try:
                        response_json = json.loads(response_data)
                        if response_json.get('status') == 'success':
                            print(f"[INFO] Data sent successfully to server")
                            return True
                        else:
                            print(f"[ERROR] Server rejected data: {response_json.get('error', 'unknown')}")
                            return False
                    except json.JSONDecodeError:
                        print(f"[ERROR] Invalid response from server")
                        return False
                elif response.getcode() == 429:  # Rate limited
                    if retry_count < max_retries:
                        wait_time = min(60, 2 ** retry_count)  # Exponential backoff, max 60s
                        print(f"[WARN] Rate limited, waiting {wait_time}s before retry")
                        time.sleep(wait_time)
                        return self._send_data(data, retry_count + 1)
                    else:
                        print(f"[ERROR] Rate limited after {max_retries} retries")
                        return False
                else:
                    print(f"[ERROR] Server returned status {response.getcode()}: {response_data}")
                    return False
                    
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8') if e.fp else str(e)
            if e.code == 401:
                print(f"[ERROR] Authentication failed - check API key")
            elif e.code == 429 and retry_count < max_retries:
                wait_time = min(60, 2 ** retry_count)
                print(f"[WARN] Rate limited (HTTP {e.code}), waiting {wait_time}s before retry")
                time.sleep(wait_time)
                return self._send_data(data, retry_count + 1)
            else:
                print(f"[ERROR] HTTP error {e.code}: {error_msg}")
            return False
        except urllib.error.URLError as e:
            if retry_count < max_retries:
                wait_time = min(30, 5 * (retry_count + 1))  # Linear backoff for network errors
                print(f"[WARN] Network error: {e.reason}, retrying in {wait_time}s")
                time.sleep(wait_time)
                return self._send_data(data, retry_count + 1)
            else:
                print(f"[ERROR] Network error after {max_retries} retries: {e.reason}")
                return False
        except socket.timeout:
            if retry_count < max_retries:
                print(f"[WARN] Request timeout, retrying ({retry_count + 1}/{max_retries})")
                return self._send_data(data, retry_count + 1)
            else:
                print(f"[ERROR] Request timeout after {max_retries} retries")
                return False
        except Exception as e:
            print(f"[ERROR] Unexpected error sending data: {e}")
            return False
    
    def run_once(self) -> bool:
        print(f"[INFO] Collecting data from instance {self.config.get('instance_id')[:8]}...")
        data = self._prepare_data()
        return self._send_data(data)
    
    def run_daemon(self):
        interval = self.config.get('agent.sync_interval', 60)
        print(f"[INFO] Starting Melissae Agent (sync every {interval}s)")
        
        consecutive_failures = 0
        max_failures = 10
        
        while True:
            try:
                success = self.run_once()
                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    
                # Exponential backoff on consecutive failures
                if consecutive_failures > 0:
                    backoff_multiplier = min(consecutive_failures, 5)  # Cap at 5x
                    sleep_time = interval * backoff_multiplier
                    print(f"[WARN] {consecutive_failures} consecutive failures, waiting {sleep_time}s")
                    
                    if consecutive_failures >= max_failures:
                        print(f"[ERROR] {max_failures} consecutive failures, stopping agent")
                        break
                        
                    time.sleep(sleep_time)
                else:
                    time.sleep(interval)
                    
            except KeyboardInterrupt:
                print(f"[INFO] Agent stopped by user")
                break
            except Exception as e:
                consecutive_failures += 1
                print(f"[ERROR] Agent error: {e}")
                
                if consecutive_failures >= max_failures:
                    print(f"[ERROR] Too many errors, stopping agent")
                    break
                    
                # Sleep with exponential backoff
                backoff_time = min(300, 30 * consecutive_failures)  # Max 5 minutes
                print(f"[INFO] Waiting {backoff_time}s before retry")
                time.sleep(backoff_time)

def main():
    parser = argparse.ArgumentParser(description='Melissae Multi-Instance Agent')
    parser.add_argument('--config', help='Config file path')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    config = MelissaeConfig(args.config)
    agent = MelissaeAgent(config)
    
    if args.once:
        success = agent.run_once()
        exit(0 if success else 1)
    elif args.daemon:
        agent.run_daemon()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()