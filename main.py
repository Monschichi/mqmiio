#!/usr/bin/env python3
import argparse
import datetime
import logging
import os
import signal
import time
from configparser import ConfigParser

from miio.devicefactory import DeviceFactory
from miio.exceptions import DeviceException

import miiomqtt


def handler(signum, frame):
    logging.error('Shutting down')
    try:
        mqtt.close()
    except NameError:
        pass
    raise SystemExit(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--verbose', action='store_const', dest='loglevel', const=logging.INFO, default=logging.WARNING,
        help='enable info logging',
    )
    parser.add_argument('--debug', action='store_const', dest='loglevel', const=logging.DEBUG, help='enable debug logging')
    parser.add_argument(
        '--config', help='config file',
        default=os.path.join(os.getcwd(), 'mqmiio.cfg'),
        type=str,
    )
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s', level=args.loglevel)

    signal.signal(signal.SIGINT, handler)

    # Read config
    config = ConfigParser()
    config.read(args.config)

    # Initialize device
    host = config.get('miio', 'host')
    token = config.get('miio', 'token')

    dev = None
    while dev is None:
        try:
            dev = DeviceFactory.create(host, token, None, force_generic_miot=True)
        except DeviceException as err:
            logging.error(f'Failed to connect to MIoT device. Retry in 10 seconds. {err}')
            time.sleep(10)

    # Initialize broker
    mqtt_host = config.get('mqtt', 'host')
    mqtt_port = int(config.get('mqtt', 'port'))
    mqtt_topic = config.get('mqtt', 'topic')
    mqtt_clientid = config.get('mqtt', 'clientid')
    mqtt_username = config.get('mqtt', 'username')
    mqtt_password = config.get('mqtt', 'password')

    mqtt = miiomqtt.MiioMqtt(dev, mqtt_host, mqtt_port, mqtt_username, mqtt_password, mqtt_clientid, mqtt_topic)

    mqtt.publish_status()
    mqtt.publish_setting()
    while True:
        try:
            mqtt.publish_status()
        except DeviceException as err:
            logging.error(f'Error occured communicating with the MIoT device: {err}')

        if datetime.datetime.now().minute % 5 == 0:
            try:
                mqtt.publish_setting()
            except DeviceException as err:
                logging.error(f'Error occured communicating with the MIoT device: {err}')

        s = 60 - (datetime.datetime.now().second % 60)
        logging.info(f'sleeping {s} seconds')
        time.sleep(s)
