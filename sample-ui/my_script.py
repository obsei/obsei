#!/usr/bin/python3
#-*- coding: utf-8 -*-

import subprocess

def send_message(message="drink water"):
    subprocess.Popen(['notify-send', message])
    return

if __name__ == '__main__':
    send_message()
