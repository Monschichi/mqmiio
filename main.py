#!/usr/bin/env python3
import argparse
import os
import signal
import time
from configparser import ConfigParser

from miio.devicefactory import DeviceFactory
from miio.exceptions import DeviceException

import miiomqtt


def handler(signum, frame):
    print('Shutting down')
    try:
        mqtt.close()
    except NameError:
        print()
    raise SystemExit(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--config', help='config file',
        default=os.path.join(os.getcwd(), 'mqmiio.cfg'),
        type=str,
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handler)

    # Read config
    config = ConfigParser()
    config.read(args.config)

    # Initialize device
    host = config.get('miio', 'host')
    token = config.get('miio', 'token')

    dev = None
    error_count = 0
    while dev is None:
        try:
            dev = DeviceFactory.create(host, token, None, force_generic_miot=True)
        except DeviceException as err:
            error_count = error_count + 1
            if error_count > 20:
                print('Failed to connect to device, terminating.')
                raise SystemExit(1)
            print(f'Failed to connect to MIoT device. Retry in 10 seconds. {err}')
            time.sleep(10)

    # Initialize broker
    mqtt_host = config.get('mqtt', 'host')
    mqtt_port = int(config.get('mqtt', 'port'))
    mqtt_topic = config.get('mqtt', 'topic')
    mqtt_clientid = config.get('mqtt', 'clientid')
    mqtt_username = config.get('mqtt', 'username')
    mqtt_password = config.get('mqtt', 'password')

    mqtt = miiomqtt.MiioMqtt(dev, mqtt_host, mqtt_port, mqtt_username, mqtt_password, mqtt_clientid, mqtt_topic)

    lastPubTime: float = 0
    lastSetTime: float = 0

    while True:
        if time.time() - lastPubTime > 5 or mqtt.publish_requested():
            try:
                mqtt.publish_status()
                lastPubTime = time.time()
                error_count = 0
            except DeviceException as err:
                error_count = error_count + 1
                print(f'Error occured communicating with the MIoT device: {err}')

        if time.time() - lastSetTime > 60 or mqtt.publish_requested():
            try:
                mqtt.publish_setting()

                lastSetTime = time.time()
            except DeviceException as err:
                error_count = error_count + 1
                print(f'Error occured communicating with the MIoT device: {err}')

        if error_count > 20:
            print('Failed to reconnect to device, terminating.')
            raise SystemExit(3)

        time.sleep(1)
