import logging
import time
from typing import Any

import paho.mqtt.client as mqtt_client
from miio.device import Device
from miio.miot_device import MiotDevice


class MiioMqtt:
    def __init__(self, device: 'MiotDevice | Device', host: str, port: int, username: str, password: str, clientid: str, topic: str) -> None:
        self.device = device
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.topic = topic
        self.client_id = clientid
        self.client = self._connect()
        self.client.miiomqtt = self
        self.mapping_topic_setting: dict[str, Any] = {}
        self._subscribe()
        self._publish(self.topic + '/connection', 'connected')
        self.client.loop_start()

    def close(self) -> None:
        self._publish(self.topic + '/connection', 'disconnected')
        self.client.loop_stop()
        self.client.disconnect()

    def _connect(self) -> mqtt_client.Client:
        def on_connect(mqttc, obj, flags, reason_code, properties):
            if reason_code == 0:
                logging.info('Connected to MQTT Broker.')
                mqttc.miiomqtt._subscribe()
            else:
                logging.error('Failed to connect to MQTT Broker, return code %d\n', reason_code)

        # Set Connecting Client ID
        client = mqtt_client.Client(client_id=self.client_id, protocol=mqtt_client.MQTTv5)
        client.on_connect = on_connect
        client.on_disconnect = self._on_disconnect

        success = False

        while not success:
            try:
                client.username_pw_set(username=self.username, password=self.password)
                client.will_set(self.topic + '/connection', 'disconnected', 2, False)
                client.connect(host=self.host, port=self.port, keepalive=60)
                success = True
            except ConnectionError as err:
                logging.error(f'Failed to connect to broker {err}. Retry in 10 seconds.')
                time.sleep(10)

        return client

    def _subscribe(self):
        settings = self.device.settings()

        for setting in settings:
            topic = self.topic + '/' + setting.replace(':', '/').replace('.', '_')
            self.client.subscribe(topic=topic, qos=2)
            self.mapping_topic_setting[topic] = setting

        self.client.on_message = self._on_message

    def _on_disconnect(self, userdata, rc, data, properties):
        reconnect_delay = 5
        client = self.client

        logging.error(f'Disconnected with result code: {rc}')
        if rc is None:
            return
        while True:
            logging.warning(f'Reconnecting in {reconnect_delay} seconds...')
            time.sleep(reconnect_delay)

            try:
                client.reconnect()
                logging.info('Reconnected successfully!')
                return
            except Exception as err:
                logging.error(f'{err}. Reconnect failed. Retrying...')

    def publish_status(self):
        devStatus = self.device.status()
        for attr in devStatus.data:
            value = str(getattr(devStatus, attr))
            topic = self.topic + '/' + attr.replace(':', '/').replace('.', '_')

            self._publish(topic, value)

    def publish_setting(self):
        settings = self.device.settings()

        for setting in settings:
            setter = settings[setting].setter
            siid = setter.args[0]
            piid = setter.args[1]
            valueObj = self.device.get_property_by(siid, piid)[0]
            topic = self.topic + '/' + setting.replace(':', '/').replace('.', '_')
            value = valueObj['value']
            self._publish(topic, str(value))

    def _on_message(self, client, userdata, msg):
        settings = self.device.settings()
        settingName = self.mapping_topic_setting[msg.topic]
        setting = settings[settingName]
        payload = msg.payload

        siid = setting.setter.args[0]
        piid = setting.setter.args[1]
        valueObj = self.device.get_property_by(siid, piid)[0]
        current_value = valueObj['value']

        if 'bool' in str(setting.type):
            value = False
            if payload.lower() == b'true':
                value = True

            if value != current_value:
                logging.info(f'bool value {settingName} changed from {current_value} to {value}')
                setting.setter(value)
                newvalueObj = self.device.get_property_by(siid, piid)[0]
                self._publish(msg.topic, str(newvalueObj['value']))
        elif 'int' in str(setting.type):
            value = int(payload)

            if value != current_value:
                logging.info(f'int value {settingName} changed from {current_value} to {value}')
                setting.setter(value)
                newvalueObj = self.device.get_property_by(siid, piid)[0]
                self._publish(msg.topic, str(newvalueObj['value']))

    def _publish(self, topic, message):
        result = self.client.publish(topic, message)
        status = result[0]
        return status
