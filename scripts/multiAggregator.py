#!/usr/bin/env python3

import os
import json
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import pytz

class MultiInstanceAggregator:
    def __init__(self, config_path: str = None):
        self.working_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = config_path or os.path.join(self.working_dir, 'multi-instance.json')
        self.config = self._load_config()
        self.output_dir = os.path.join(self.working_dir, 'dashboard/json')
        
    def _load_config(self) -> Dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _normalize_timezone(self, date_str: str, hour_str: str, source_timezone: str) -> tuple:
        """Normalize timestamp to UTC for consistent sorting"""
        try:
            # Parse the original timestamp
            dt_str = f"{date_str} {hour_str}"
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            
            # Apply source timezone
            if source_timezone and source_timezone != 'UTC':
                try:
                    tz = pytz.timezone(source_timezone)
                    dt = tz.localize(dt)
                    dt = dt.astimezone(pytz.UTC)
                except:
                    # If timezone parsing fails, assume UTC
                    dt = dt.replace(tzinfo=pytz.UTC)
            else:
                dt = dt.replace(tzinfo=pytz.UTC)
            
            return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M:%S')
        except:
            # Return original values if parsing fails
            return date_str, hour_str
    
    def _fetch_aggregated_data(self) -> tuple:
        """Fetch aggregated data from the multi-instance server"""
        server_config = self.config.get('server', {})
        api_key = server_config.get('api_key')
        port = server_config.get('port', 8888)
        
        if not api_key:
            print("[ERROR] No API key configured for server access")
            return [], []
        
        try:
            url = f"http://localhost:{port}/api/aggregated"
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('logs', []), data.get('threats', [])
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch data from server: {e}")
            return [], []
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid response from server: {e}")
            return [], []
    
    def _fetch_instances_data(self) -> List[Dict]:
        """Fetch instance information from the multi-instance server"""
        server_config = self.config.get('server', {})
        api_key = server_config.get('api_key')
        port = server_config.get('port', 8888)
        
        if not api_key:
            return []
        
        try:
            url = f"http://localhost:{port}/api/instances"
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('instances', [])
            
        except:
            return []
    
    def _merge_local_and_remote_data(self, remote_logs: List[Dict], remote_threats: List[Dict]) -> tuple:
        """Merge local logs with remote multi-instance data"""
        # Load local data
        local_logs = self._load_local_logs()
        local_threats = self._load_local_threats()
        
        # Combine and deduplicate
        all_logs = []
        all_threats = []
        seen_logs = set()
        seen_threats = set()
        
        # Process local logs first
        for log in local_logs:
            log_copy = log.copy()
            log_copy['instance_id'] = self.config.get('instance_id', 'local')
            log_copy['hostname'] = 'localhost'
            
            log_hash = self._create_log_hash(log)
            if log_hash not in seen_logs:
                seen_logs.add(log_hash)
                all_logs.append(log_copy)
        
        # Process local threats
        for threat in local_threats:
            threat_copy = threat.copy()
            threat_copy['instance_id'] = self.config.get('instance_id', 'local')
            threat_copy['hostname'] = 'localhost'
            
            threat_hash = self._create_threat_hash(threat)
            if threat_hash not in seen_threats:
                seen_threats.add(threat_hash)
                all_threats.append(threat_copy)
        
        # Add remote data (already deduplicated by server)
        for log in remote_logs:
            log_hash = self._create_log_hash(log)
            if log_hash not in seen_logs:
                seen_logs.add(log_hash)
                all_logs.append(log)
        
        for threat in remote_threats:
            threat_hash = self._create_threat_hash(threat)
            if threat_hash not in seen_threats:
                seen_threats.add(threat_hash)
                all_threats.append(threat)
        
        return all_logs, all_threats
    
    def _create_log_hash(self, log: Dict) -> str:
        """Create hash for log deduplication"""
        hash_data = {
            k: v for k, v in log.items() 
            if k not in ['instance_id', 'hostname']
        }
        return hashlib.md5(json.dumps(hash_data, sort_keys=True).encode()).hexdigest()
    
    def _create_threat_hash(self, threat: Dict) -> str:
        """Create hash for threat deduplication"""
        hash_data = {
            k: v for k, v in threat.items() 
            if k not in ['instance_id', 'hostname']
        }
        return hashlib.md5(json.dumps(hash_data, sort_keys=True).encode()).hexdigest()
    
    def _load_local_logs(self) -> List[Dict]:
        """Load local logs.json file"""
        logs_path = os.path.join(self.output_dir, 'logs.json')
        if os.path.exists(logs_path):
            try:
                with open(logs_path, 'r') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except (json.JSONDecodeError, IOError):
                pass
        return []
    
    def _load_local_threats(self) -> List[Dict]:
        """Load local threats.json file"""
        threats_path = os.path.join(self.output_dir, 'threats.json')
        if os.path.exists(threats_path):
            try:
                with open(threats_path, 'r') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except (json.JSONDecodeError, IOError):
                pass
        return []
    
    def _sort_logs_by_timestamp(self, logs: List[Dict]) -> List[Dict]:
        """Sort logs by normalized timestamp"""
        def sort_key(log):
            try:
                date_str = log.get('date', '')
                hour_str = log.get('hour', '')
                instance_tz = log.get('timezone', 'UTC')
                
                # Normalize to UTC for sorting
                norm_date, norm_hour = self._normalize_timezone(date_str, hour_str, instance_tz)
                return datetime.strptime(f"{norm_date} {norm_hour}", '%Y-%m-%d %H:%M:%S')
            except:
                return datetime.min
        
        return sorted(logs, key=sort_key)
    
    def _recalculate_threats(self, logs: List[Dict]) -> List[Dict]:
        """Recalculate threat scores based on aggregated logs"""
        # Group logs by IP across all instances
        ip_data = defaultdict(list)
        for log in logs:
            ip = log.get('ip', '')
            if ip:
                ip_data[ip].append(log)
        
        threats = []
        for ip, entries in ip_data.items():
            if not ip:
                continue
            
            score = self._calculate_protocol_score(entries)
            verdict = self._get_verdict(score)
            
            # Get instance information for this IP
            instances = list(set(entry.get('instance_id', 'unknown') for entry in entries))
            hostnames = list(set(entry.get('hostname', 'unknown') for entry in entries))
            
            threat = {
                "type": "ip",
                "ip": ip,
                "protocol-score": score,
                "verdict": verdict,
                "instances": instances,
                "hostnames": hostnames,
                "activity_count": len(entries)
            }
            threats.append(threat)
        
        return threats
    
    def _calculate_protocol_score(self, ip_data: List[Dict]) -> int:
        """Calculate protocol score (from threatIntel.py logic)"""
        http_count = 0
        ssh_failed = False
        ssh_success = False
        ftp_failed = False
        ftp_success = False
        modbus_write = False
        modbus_read = False

        for entry in ip_data:
            protocol = entry.get('protocol', '').upper()
            action = entry.get('action', '').lower()

            if protocol == 'HTTP':
                http_count += 1
            elif protocol == 'SSH':
                if 'failed' in action:
                    ssh_failed = True
                elif 'successful' in action:
                    ssh_success = True
            elif protocol == 'FTP':
                if 'failed' in action:
                    ftp_failed = True
                elif 'successful' in action:
                    ftp_success = True
            elif protocol == 'MODBUS':
                if 'write' in action:
                    modbus_write = True
                elif 'read' in action:
                    modbus_read = True

        # Nefarious - Multiple successful compromises or Modbus writes and one successful compromise
        if (ssh_success and ftp_success) or (modbus_write and (ssh_success or ftp_success)):
            return 5

        # Malicious - Single successful compromise or multiple protocols failed with Modbus writes
        elif (ssh_success or ftp_success) or (modbus_write and (ssh_failed or ftp_failed)):
            return 4

        # Suspicious - Failed attempts or excessive HTTP or Modbus reconnaissance
        elif http_count > 50 or ssh_failed or ftp_failed or modbus_read:
            return 2

        # Benign
        else:
            return 1
    
    def _get_verdict(self, score: int) -> str:
        """Get verdict from score"""
        verdicts = {
            1: "benign",
            2: "suspicious", 
            4: "malicious",
            5: "nefarious"
        }
        return verdicts.get(score, "unknown")
    
    def _save_aggregated_data(self, logs: List[Dict], threats: List[Dict], instances: List[Dict] = None):
        """Save aggregated data to JSON files"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Save aggregated logs
        logs_path = os.path.join(self.output_dir, 'logs-aggregated.json')
        with open(logs_path, 'w') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        
        # Save aggregated threats
        threats_path = os.path.join(self.output_dir, 'threats-aggregated.json')
        with open(threats_path, 'w') as f:
            json.dump(threats, f, indent=2, ensure_ascii=False)
        
        # Save instance data if available
        if instances is not None:
            instances_path = os.path.join(self.output_dir, 'multi-instance.json')
            with open(instances_path, 'w') as f:
                json.dump({'instances': instances}, f, indent=2, ensure_ascii=False)
        
        print(f"[INFO] Saved {len(logs)} aggregated logs and {len(threats)} threats")
    
    def aggregate(self):
        """Main aggregation function"""
        print("[INFO] Starting multi-instance aggregation...")
        
        instances = None
        
        # Check if we're in server mode
        if self.config.get('mode') == 'server':
            # Fetch data from the multi-instance server
            remote_logs, remote_threats = self._fetch_aggregated_data()
            
            # Fetch instance information
            instances = self._fetch_instances_data()
            
            # Merge with local data
            all_logs, all_threats = self._merge_local_and_remote_data(remote_logs, remote_threats)
        else:
            # Standalone mode - just use local data
            all_logs = self._load_local_logs()
            all_threats = self._load_local_threats()
        
        # Sort logs by timestamp
        all_logs = self._sort_logs_by_timestamp(all_logs)
        
        # Recalculate threats based on aggregated data
        recalculated_threats = self._recalculate_threats(all_logs)
        
        # Save aggregated data
        self._save_aggregated_data(all_logs, recalculated_threats, instances)
        
        print(f"[INFO] Aggregation complete: {len(all_logs)} logs, {len(recalculated_threats)} unique IPs")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Melissae Multi-Instance Data Aggregator')
    parser.add_argument('--config', help='Config file path')
    
    args = parser.parse_args()
    
    aggregator = MultiInstanceAggregator(args.config)
    aggregator.aggregate()

if __name__ == "__main__":
    main()