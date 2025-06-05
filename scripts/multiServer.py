#!/usr/bin/env python3

import os
import json
import time
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from typing import Dict, List
import threading
import ipaddress
import logging

class MelissaeServerHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, server_instance=None, **kwargs):
        self.server_instance = server_instance
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        client_ip = self.client_address[0]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {client_ip} - {format % args}")
    
    def _send_response(self, code: int, data: Dict = None, content_type: str = 'application/json'):
        # Security headers
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-XSS-Protection', '1; mode=block')
        self.send_header('Server', 'Melissae-MultiInstance/1.0')
        
        # CORS headers (restrictive)
        allowed_origins = self.server_instance.config.get('server.allowed_origins', ['http://localhost:9999'])
        origin = self.headers.get('Origin', '')
        if origin in allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '3600')
        
        self.end_headers()
        
        if data:
            response_data = json.dumps(data).encode('utf-8')
            self.wfile.write(response_data)
    
    def _rate_limit_check(self) -> bool:
        """Simple rate limiting based on client IP"""
        client_ip = self.client_address[0]
        current_time = time.time()
        
        # Clean old entries (older than 1 minute)
        cutoff_time = current_time - 60
        self.server_instance.rate_limits = {
            ip: times for ip, times in self.server_instance.rate_limits.items()
            if any(t > cutoff_time for t in times)
        }
        
        # Update rate limit for current IP
        if client_ip not in self.server_instance.rate_limits:
            self.server_instance.rate_limits[client_ip] = []
        
        # Remove old timestamps for this IP
        self.server_instance.rate_limits[client_ip] = [
            t for t in self.server_instance.rate_limits[client_ip] if t > cutoff_time
        ]
        
        # Check if rate limit exceeded (max 60 requests per minute)
        if len(self.server_instance.rate_limits[client_ip]) >= 60:
            return False
        
        # Add current timestamp
        self.server_instance.rate_limits[client_ip].append(current_time)
        return True
    
    def _authenticate(self) -> bool:
        """Enhanced authentication with timing attack protection"""
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            # Use constant time comparison to prevent timing attacks
            hmac.compare_digest("dummy", "dummy")
            return False
        
        token = auth_header[7:]
        expected_token = self.server_instance.config.get('server', {}).get('api_key', '')
        
        # Constant time comparison
        return hmac.compare_digest(token, expected_token)
    
    def _validate_request_size(self, max_size: int = 10 * 1024 * 1024) -> bool:
        """Validate request size to prevent DoS attacks"""
        content_length = self.headers.get('Content-Length')
        if content_length:
            try:
                size = int(content_length)
                return size <= max_size
            except ValueError:
                return False
        return True
    
    def do_OPTIONS(self):
        if not self._rate_limit_check():
            self._send_response(429, {"error": "Rate limit exceeded"})
            return
        self._send_response(200)
    
    def do_GET(self):
        try:
            # Rate limiting check
            if not self._rate_limit_check():
                self._send_response(429, {"error": "Rate limit exceeded"})
                return
            
            parsed_path = urlparse(self.path)
            
            if parsed_path.path == '/api/status':
                self._send_response(200, {
                    "status": "running",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "connected_instances": len(self.server_instance.instances)
                })
            elif parsed_path.path == '/api/instances':
                if not self._authenticate():
                    self._send_response(401, {"error": "Unauthorized"})
                    return
                
                instances = []
                for instance_id, data in self.server_instance.instances.items():
                    last_seen = data.get('last_seen', '')
                    instances.append({
                        "instance_id": instance_id,
                        "hostname": data.get('hostname', ''),
                        "last_seen": last_seen,
                        "stats": data.get('stats', {})
                    })
                
                self._send_response(200, {"instances": instances})
            elif parsed_path.path == '/api/aggregated':
                if not self._authenticate():
                    self._send_response(401, {"error": "Unauthorized"})
                    return
                
                try:
                    logs, threats = self.server_instance.get_aggregated_data()
                    self._send_response(200, {
                        "logs": logs,
                        "threats": threats,
                        "stats": {
                            "total_logs": len(logs),
                            "total_threats": len(threats),
                            "instances": len(self.server_instance.instances)
                        }
                    })
                except Exception as e:
                    print(f"[ERROR] Failed to get aggregated data: {e}")
                    self._send_response(500, {"error": "Internal server error"})
            else:
                self._send_response(404, {"error": "Not found"})
                
        except Exception as e:
            print(f"[ERROR] GET request error: {e}")
            self._send_response(500, {"error": "Internal server error"})
    
    def do_POST(self):
        try:
            # Rate limiting check
            if not self._rate_limit_check():
                self._send_response(429, {"error": "Rate limit exceeded"})
                return
            
            # Request size validation
            if not self._validate_request_size():
                self._send_response(413, {"error": "Request too large"})
                return
            
            parsed_path = urlparse(self.path)
            
            if parsed_path.path == '/api/data':
                if not self._authenticate():
                    self._send_response(401, {"error": "Unauthorized"})
                    return
                
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length == 0:
                        self._send_response(400, {"error": "Empty request"})
                        return
                    
                    post_data = self.rfile.read(content_length)
                    
                    # Validate JSON format
                    try:
                        data = json.loads(post_data.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        print(f"[ERROR] Invalid JSON data: {e}")
                        self._send_response(400, {"error": "Invalid JSON format"})
                        return
                    
                    # Validate required fields
                    if not isinstance(data, dict) or 'instance_id' not in data:
                        self._send_response(400, {"error": "Missing required fields"})
                        return
                    
                    if self.server_instance.store_instance_data(data):
                        self._send_response(200, {"status": "success"})
                    else:
                        self._send_response(400, {"error": "Invalid data"})
                        
                except Exception as e:
                    print(f"[ERROR] Processing POST data: {e}")
                    self._send_response(500, {"error": "Internal server error"})
            else:
                self._send_response(404, {"error": "Not found"})
                
        except Exception as e:
            print(f"[ERROR] POST request error: {e}")
            self._send_response(500, {"error": "Internal server error"})

class MelissaeServer:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'multi-instance.json')
        self.working_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.working_dir, 'multi-instance-data')
        self.config = self._load_config()
        self.instances = {}
        self.rate_limits = {}  # For rate limiting
        self._load_instance_data()
        
        # Create data directory with secure permissions
        os.makedirs(self.data_dir, exist_ok=True)
        os.chmod(self.data_dir, 0o750)  # rwxr-x---
    
    def _load_config(self) -> Dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _load_instance_data(self):
        instances_file = os.path.join(self.data_dir, 'instances.json')
        if os.path.exists(instances_file):
            try:
                with open(instances_file, 'r') as f:
                    self.instances = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.instances = {}
    
    def _save_instance_data(self):
        instances_file = os.path.join(self.data_dir, 'instances.json')
        try:
            with open(instances_file, 'w') as f:
                json.dump(self.instances, f, indent=2)
        except IOError as e:
            print(f"[ERROR] Failed to save instance data: {e}")
    
    def store_instance_data(self, data: Dict) -> bool:
        try:
            instance_id = data.get('instance_id')
            if not instance_id:
                return False
            
            # Store current timestamp
            data['last_seen'] = datetime.now(timezone.utc).isoformat()
            
            # Update instances registry
            self.instances[instance_id] = {
                'hostname': data.get('hostname', ''),
                'last_seen': data['last_seen'],
                'timezone': data.get('timezone', 'UTC'),
                'stats': data.get('stats', {})
            }
            
            # Save individual instance data
            instance_file = os.path.join(self.data_dir, f'{instance_id}.json')
            with open(instance_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self._save_instance_data()
            print(f"[INFO] Stored data from instance {instance_id[:8]}...")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to store instance data: {e}")
            return False
    
    def get_aggregated_data(self) -> tuple:
        all_logs = []
        all_threats = []
        seen_logs = set()
        seen_threats = set()
        
        # Load data from all instances
        for instance_id in self.instances.keys():
            instance_file = os.path.join(self.data_dir, f'{instance_id}.json')
            if os.path.exists(instance_file):
                try:
                    with open(instance_file, 'r') as f:
                        data = json.load(f)
                    
                    # Process logs
                    for log in data.get('logs', []):
                        # Add instance metadata
                        log_with_instance = log.copy()
                        log_with_instance['instance_id'] = instance_id
                        log_with_instance['hostname'] = data.get('hostname', '')
                        
                        # Create hash for deduplication
                        log_hash = hashlib.md5(json.dumps({
                            k: v for k, v in log.items() 
                            if k not in ['instance_id', 'hostname']
                        }, sort_keys=True).encode()).hexdigest()
                        
                        if log_hash not in seen_logs:
                            seen_logs.add(log_hash)
                            all_logs.append(log_with_instance)
                    
                    # Process threats
                    for threat in data.get('threats', []):
                        threat_with_instance = threat.copy()
                        threat_with_instance['instance_id'] = instance_id
                        threat_with_instance['hostname'] = data.get('hostname', '')
                        
                        threat_hash = hashlib.md5(json.dumps({
                            k: v for k, v in threat.items() 
                            if k not in ['instance_id', 'hostname']
                        }, sort_keys=True).encode()).hexdigest()
                        
                        if threat_hash not in seen_threats:
                            seen_threats.add(threat_hash)
                            all_threats.append(threat_with_instance)
                
                except (json.JSONDecodeError, IOError) as e:
                    print(f"[ERROR] Failed to load data for instance {instance_id}: {e}")
        
        # Sort by timestamp
        all_logs.sort(key=lambda x: f"{x.get('date', '')} {x.get('hour', '')}")
        
        return all_logs, all_threats
    
    def start_server(self):
        host = self.config.get('server', {}).get('host', '0.0.0.0')
        port = self.config.get('server', {}).get('port', 8888)
        
        def handler(*args, **kwargs):
            return MelissaeServerHandler(*args, server_instance=self, **kwargs)
        
        try:
            server = HTTPServer((host, port), handler)
            print(f"[INFO] Melissae Multi-Instance Server starting on {host}:{port}")
            print(f"[INFO] API Key: {self.config.get('server', {}).get('api_key', 'NOT_SET')}")
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[INFO] Server stopped by user")
        except Exception as e:
            print(f"[ERROR] Server error: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Melissae Multi-Instance Server')
    parser.add_argument('--config', help='Config file path')
    
    args = parser.parse_args()
    
    server = MelissaeServer(args.config)
    server.start_server()

if __name__ == "__main__":
    main()