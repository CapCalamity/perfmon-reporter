#!/usr/bin/python3.4

import json
import psutil
import requests
import socket
import urllib.parse
import threading
from subprocess import call
from os import path

class SysReporter:
    def __init__(self):
        self.prev_info = {}

    def start(self):
        self.send_system_info()

    def gather_system_info(self):
        disk_partitions = psutil.disk_partitions()
        disk_usage = {}
  
        for disk in disk_partitions:
            disk_usage[disk.device] = self.to_dict(psutil.disk_usage(disk.mountpoint))
  
        net_io_counters = {}
        for name, nic in psutil.net_io_counters(pernic=True).items():
            net_io_counters[name] = self.to_dict(nic)
            
            if self.prev_info:
                net_io_counters[name]['bytes_sent_sec'] = net_io_counters[name]['bytes_sent'] - self.prev_info['net_io'][name]['bytes_sent']
                net_io_counters[name]['bytes_recv_sec'] = net_io_counters[name]['bytes_recv'] - self.prev_info['net_io'][name]['bytes_recv']
                net_io_counters[name]['packets_sent_sec'] = net_io_counters[name]['packets_sent'] - self.prev_info['net_io'][name]['packets_sent']
                net_io_counters[name]['packets_recv_sec'] = net_io_counters[name]['packets_recv'] - self.prev_info['net_io'][name]['packets_recv']
            else:
                net_io_counters[name]['bytes_sent_sec'] = 0
                net_io_counters[name]['bytes_recv_sec'] = 0
                net_io_counters[name]['packets_sent_sec'] = 0
                net_io_counters[name]['packets_recv_sec'] = 0
                
        info = {
            'cpu_count': psutil.cpu_count(),
            'cpu_count_physical': psutil.cpu_count(logical=False),
            'cpu_percent': self.to_dict(psutil.cpu_percent(percpu=True)),
            'cpu_times': self.to_dict(psutil.cpu_times()),
            'cpu_times_percent': self.to_dict(psutil.cpu_times_percent()),
            'memory_virtual': self.to_dict(psutil.virtual_memory()),
            'memory_swap': self.to_dict(psutil.swap_memory()),
            'disk_partitions': self.to_dict(disk_partitions),
            'disk_usage': disk_usage,
            'net_io': net_io_counters,
            'users': self.to_dict(psutil.users()),
            'boot_time': psutil.boot_time(),
            'hostname': socket.gethostname(),
        }
  
        self.prev_info = info

        return info
  
    def to_dict(self, obj):
        if isinstance(obj, list):
            temp = []
            for item in obj:
                temp.append(self.to_dict(item))
        else:
            temp = {}
            for key in [x for x in dir(obj) if 
                          not x.startswith('__') 
                          and not x.startswith('_')
                          and not callable(getattr(obj, x))]:
                temp[key] = getattr(obj, key)
        return temp
  
    def send_system_info(self):
        # schedule the next interval immediately
        threading.Timer(1.0, self.send_system_info).start()

        uuid_file = '.perfmon_id'
        uuid = ''
        if not path.isfile(uuid_file):
            call(['cat', '/proc/sys/kernel/random/uuid > ' + uuid_file])
      
        if path.isfile(uuid_file):
            with open(uuid_file, 'r') as file:
                uuid = file.read().strip()
        else:
            return
      
        data = {
            'info': json.dumps(self.gather_system_info()),
            'uuid': uuid
        }
      
        headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
        
        r = requests.post('http://localhost:8000/record', data=urllib.parse.urlencode(data), headers=headers)
        if r.status_code != 200:
            print(r.status_code, r.reason, r.text)

# program start
# gather system information with psutils, pack them in a nice format and send
# them of to the perfmon
gen = SysReporter()
gen.start()

