#!/usr/bin/python3.4

import sys
import argparse
import curses
import json
import psutil
import requests
import socket
import urllib.parse
import threading
from subprocess import call
from os import path
from datetime import datetime
import time

class SysReporter:
    def __init__(self, args):
        self.prev_info = {}
        self.stdsceen = None
        self.window = None

        self.host = args.host
        self.interval = args.interval
        self.quiet = args.quiet

    def start(self, stdscreen=None):
        self.run = True

        if not self.quiet and stdscreen:
            self.screen = stdscreen
            self.window = curses.newwin(10, curses.COLS - 1)

        self.send_system_info()

        try:
            while self.run:
                start = datetime.now()
                response = self.send_system_info()
                end = datetime.now()
                diff = end - start

                sleep_duration = 0.0
                if(diff.total_seconds() < 1.0):
                    sleep_duration = 1.0 - diff.total_seconds()

                if not self.quiet:        
                    self.window.erase()

                    self.window.addstr(0, 0, '{}'.format(datetime.now()))
                    self.window.addstr(1, 0, '{} - {}'.format(response.status_code, response.reason))
                    self.window.addstr(2, 0, '{}'.format(response.text))
                    self.window.addstr(3, 0, '{}'.format(sleep_duration))

                    self.window.refresh()

                time.sleep(sleep_duration)
        except Exception as exception:
            print('Exception encountered: {}'.format(exception))
            return

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
           
        return requests.post('{}/record'.format(self.host), data=urllib.parse.urlencode(data), headers=headers)

# program start

# gather system information with psutils, pack them in a nice format and send
# them of to the perfmon
        
parser = argparse.ArgumentParser()
parser.add_argument('host', help='address to the perfmon site')
parser.add_argument('-i', '--interval', help='interval in seconds at which the system information is reported')
parser.add_argument('-q', '--quiet', help='do not generate output', action='store_true')

args = parser.parse_args()
gen = SysReporter(args)

if not args.quiet:
    stdscreen = curses.initscr()

try:
    if not args.quiet:
        curses.noecho()
        curses.cbreak()
        stdscreen.keypad(True)
        gen.start(stdscreen)
    else:
        gen.start()
except:
    if not args.quiet:
        curses.echo()
        curses.nocbreak()
        stdscreen.keypad(False)
        curses.endwin()

    sys.exit()

