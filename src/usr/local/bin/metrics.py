#!/usr/bin/python3

import psutil
import json
from datetime import datetime
import socket
import platform
from datetime import timedelta
import os
import time

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (float)):
            return round(obj, 3)
        return super().default(obj)

def get_cpu_data():
    # Initialize CPU metrics
    psutil.cpu_percent(percpu=True)
    psutil.cpu_times_percent(percpu=True)
    
    # Wait to gather data
    time.sleep(1)
    
    # Get CPU percentages and times
    cpu_percents = psutil.cpu_percent(percpu=True)
    cpu_times = psutil.cpu_times_percent(percpu=True)
    
    # Get load averages
    load1, load5, load15 = os.getloadavg()
    
    cpu_data = {
        'cores': psutil.cpu_count(logical=True),
        'cores_physical': psutil.cpu_count(logical=False),
        'load': {
            '1m': round(load1, 3),
            '5m': round(load5, 3),
            '15m': round(load15, 3)
        }
    }
    
    for i, (percent, times) in enumerate(zip(cpu_percents, cpu_times)):
        core_prefix = f'core.{i}'
        cpu_data[f'{core_prefix}.pct'] = round(percent, 3)
        cpu_data[f'{core_prefix}.user.pct'] = round(times.user, 3)
        cpu_data[f'{core_prefix}.nice.pct'] = round(times.nice, 3)
        cpu_data[f'{core_prefix}.system.pct'] = round(times.system, 3)
        cpu_data[f'{core_prefix}.idle.pct'] = round(times.idle, 3)
        cpu_data[f'{core_prefix}.iowait.pct'] = round(getattr(times, 'iowait', 0), 3)
        cpu_data[f'{core_prefix}.irq.pct'] = round(getattr(times, 'irq', 0), 3)
        cpu_data[f'{core_prefix}.softirq.pct'] = round(getattr(times, 'softirq', 0), 3)
        cpu_data[f'{core_prefix}.steal.pct'] = round(getattr(times, 'steal', 0), 3)
    
    return cpu_data

def get_network_data():
    network_data = {}
    
    # Network interfaces
    net_if_addrs = psutil.net_if_addrs()
    net_io = psutil.net_io_counters(pernic=True)
    
    for interface, addrs in net_if_addrs.items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                prefix = f'interface.{interface}'
                network_data[f'{prefix}.ip'] = addr.address
                network_data[f'{prefix}.netmask'] = addr.netmask
                
                if interface in net_io:
                    counters = net_io[interface]
                    network_data[f'{prefix}.in.bytes'] = counters.bytes_recv
                    network_data[f'{prefix}.in.packets'] = counters.packets_recv
                    network_data[f'{prefix}.in.errors'] = counters.errin
                    network_data[f'{prefix}.in.dropped'] = counters.dropin
                    network_data[f'{prefix}.out.bytes'] = counters.bytes_sent
                    network_data[f'{prefix}.out.packets'] = counters.packets_sent
                    network_data[f'{prefix}.out.errors'] = counters.errout
                    network_data[f'{prefix}.out.dropped'] = counters.dropout
    
    return network_data

def get_system_metrics():
    # Get timestamp in ISO format with timezone
    timestamp = datetime.now().astimezone().isoformat()
    
    metrics = {
        '@timestamp': timestamp,
        'event': {
            'kind': 'metric',
            'category': 'host',
            'type': 'info'
        },
        'host': {
            'hostname': platform.node(),
            'os': {
                'name': 'linux',
                'kernel': platform.release(),
                'full': platform.uname().version
            },
            'uptime': int(time.time() - psutil.boot_time())
        },
        'system': {
            'cpu': get_cpu_data()
        }
    }
    
    # Memory metrics
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    
    metrics['system']['memory'] = {
        'total': vm.total,
        'used.bytes': vm.used,
        'free': vm.free,
        'actual': {
            'free': vm.available,
            'used.bytes': vm.total - vm.available,
            'used.pct': round(vm.percent, 3)
        },
        'swap': {
            'total': sm.total,
            'used.bytes': sm.used,
            'free': sm.free,
            'used.pct': round(sm.percent, 3)
        }
    }
    
    # Filesystem metrics
    virtual_filesystems = {'devtmpfs', 'tmpfs', 'devfs', 'ramfs', 'proc', 'sysfs', 'debugfs', 'cgroup2fs'}
    metrics['system']['filesystem'] = {}
    
    for partition in psutil.disk_partitions(all=False):
        if partition.fstype not in virtual_filesystems:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                device_name = partition.device.replace('/', '_').lstrip('_')
                fs_data = {
                    'type': partition.fstype,
                    'mount_point': partition.mountpoint,
                    'total': usage.total,
                    'used.bytes': usage.used,
                    'used.pct': round(usage.percent, 3),
                    'free': usage.free
                }
                metrics['system']['filesystem'][device_name] = fs_data
            except (PermissionError, OSError):
                continue
    
    # Disk I/O metrics
    metrics['system']['diskio'] = {}
    disk_io = psutil.disk_io_counters(perdisk=True)
    for disk_name, counters in disk_io.items():
        if not disk_name.startswith('loop'):
            metrics['system']['diskio'][disk_name] = {
                'read.bytes': counters.read_bytes,
                'write.bytes': counters.write_bytes,
                'read.count': counters.read_count,
                'write.count': counters.write_count,
                'io.time': counters.read_time + counters.write_time,
                'busy_time': getattr(counters, 'busy_time', None)
            }
    
    # Network metrics
    metrics['system']['network'] = get_network_data()
    
    return metrics

if __name__ == '__main__':
    import sys
    
    if not platform.system() == 'Linux':
        print(json.dumps({"error": "This script is intended for Linux systems only"}))
        sys.exit(1)
        
    metrics = get_system_metrics()
    print(json.dumps(metrics, separators=(',', ':'), cls=CustomJSONEncoder))
