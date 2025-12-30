import time
from typing import Any

import paho.mqtt.client as mqtt_client
from miio.device import Device


class MiioMqtt:
    def __init__(self, device: Device, host: str, port: int, username: str, password: str, clientid: str, topic: str) -> None:
        self.device = device
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.topic = topic
        self.client_id = clientid
        self.client = self._connect()
        self.client.miiomqtt = self
        self.publish_req = False
        self.mapping_topic_setting: dict[str, Any] = {}
        self._subscribe()
        self._publish(self.topic + '/connection', 'connected')
        self.client.loop_start()

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish_requested(self) -> bool:
        if self.publish_req:
            self.publish_req = False
            return True
        else:
            return False

    def _connect(self) -> mqtt_client.Client:
        def on_connect(mqttc, obj, flags, reason_code, properties):
            if reason_code == 0:
                print('Connected to MQTT Broker.')
                mqttc.miiomqtt._subscribe()
            else:
                print('Failed to connect to MQTT Broker, return code %d\n', reason_code)

        # Set Connecting Client ID
        client = mqtt_client.Client(client_id=self.client_id, protocol=mqtt_client.MQTTv5)
        client.on_connect = on_connect
        client.on_disconnect = self._on_disconnect

        success = False

        while not success:
            try:
                client.username_pw_set(username=self.username, password=self.password)
                client.will_set(self.topic + '/connection', 'disconnected', 2, False)
                client.connect(host=self.host, port=self.port)
                success = True
            except ConnectionError as err:
                print(f'Failed to connect to broker {err}. Retry in 10 seconds.')
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

        print(f'Disconnected with result code: {rc}')
        while True:
            print(f'Reconnecting in {reconnect_delay} seconds...')
            time.sleep(reconnect_delay)

            try:
                client.reconnect()
                print('Reconnected successfully!')
                return
            except Exception as err:
                print(f'{err}. Reconnect failed. Retrying...')

        # print.info("Reconnect failed after %s attempts. Exiting...", reconnect_count)

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

    def _on_message(client, userdata, msg, data):
        self = userdata.miiomqtt
        settings = self.device.settings()
        settingName = self.mapping_topic_setting[data.topic]
        setting = settings[settingName]
        payload = data.payload

        siid = setting.setter.args[0]
        piid = setting.setter.args[1]
        valueObj = self.device.get_property_by(siid, piid)[0]
        current_value = valueObj['value']

        if 'bool' in str(setting.type):
            value = False
            if payload.lower() == b'true':
                value = True

            if value != current_value:
                print(f'bool value {settingName} change from {current_value} to {value}')
                setting.setter(value)
                self.publish_req = True
        elif 'int' in str(setting.type):
            value = int(payload)

            if value != current_value:
                print(f'int value {settingName} change from {current_value} to {value}')
                setting.setter(value)
                self.publish_req = True

    def _publish(self, topic, message):
        result = self.client.publish(topic, message)
        status = result[0]
        return status
