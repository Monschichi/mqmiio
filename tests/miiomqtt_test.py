import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from miiomqtt import MiioMqtt


class TestMiioMqtt(unittest.TestCase):
    def setUp(self):
        self.device_mock = MagicMock()
        self.device_mock.settings.return_value = {
            'test_setting:bool': MagicMock(
                setter=MagicMock(args=[1, 2]),
                type='bool',
            ),
            'test_setting:int': MagicMock(
                setter=MagicMock(args=[3, 4]),
                type='int',
            ),
        }
        self.bool_value = False
        self.int_value = 10

        def get_property_by_mock(siid, piid):
            if siid == 1 and piid == 2:
                return [{'value': self.bool_value}]
            if siid == 3 and piid == 4:
                return [{'value': self.int_value}]
            return MagicMock()

        self.device_mock.get_property_by.side_effect = get_property_by_mock

        def set_bool_value(value):
            self.bool_value = value

        def set_int_value(value):
            self.int_value = value

        self.device_mock.settings.return_value['test_setting:bool'].setter.side_effect = set_bool_value
        self.device_mock.settings.return_value['test_setting:int'].setter.side_effect = set_int_value
        self.device_mock.status.return_value = MagicMock(
            data={'test_status': 'ok'},
            test_status='ok',
        )

        self.mqtt_client_mock = MagicMock()

        self.patches = [
            patch('miiomqtt.mqtt_client.Client', return_value=self.mqtt_client_mock),
        ]

        for p in self.patches:
            p.start()

        self.miio_mqtt = MiioMqtt(
            device=self.device_mock,
            host='localhost',
            port=1883,
            username='user',
            password='password',
            clientid='test_client',
            topic='test_topic',
        )

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_init(self):
        self.mqtt_client_mock.username_pw_set.assert_called_with(username='user', password='password')
        self.mqtt_client_mock.will_set.assert_called_with('test_topic/connection', 'disconnected', 2, False)
        self.mqtt_client_mock.connect.assert_called_with(host='localhost', port=1883, keepalive=60)
        self.mqtt_client_mock.loop_start.assert_called_once()
        self.assertEqual(self.miio_mqtt.client, self.mqtt_client_mock)
        self.assertIn('test_topic/test_setting/bool', self.miio_mqtt.mapping_topic_setting)
        self.assertIn('test_topic/test_setting/int', self.miio_mqtt.mapping_topic_setting)
        self.mqtt_client_mock.subscribe.assert_any_call(topic='test_topic/test_setting/bool', qos=2)
        self.mqtt_client_mock.subscribe.assert_any_call(topic='test_topic/test_setting/int', qos=2)
        self.mqtt_client_mock.publish.assert_called_with('test_topic/connection', 'connected')

    def test_close(self):
        self.miio_mqtt.close()
        self.mqtt_client_mock.loop_stop.assert_called_once()
        self.mqtt_client_mock.disconnect.assert_called_once()

    def test_publish_status(self):
        self.miio_mqtt.publish_status()
        self.mqtt_client_mock.publish.assert_called_with('test_topic/test_status', 'ok')

    def test_publish_setting(self):
        self.miio_mqtt.publish_setting()
        self.mqtt_client_mock.publish.assert_any_call('test_topic/test_setting/bool', 'False')
        self.mqtt_client_mock.publish.assert_any_call('test_topic/test_setting/int', '10')

    def test_on_message_bool(self):
        msg = MagicMock()
        msg.topic = 'test_topic/test_setting/bool'
        msg.payload = b'true'
        self.miio_mqtt.client.on_message(self.mqtt_client_mock, self.miio_mqtt, msg)

        self.device_mock.settings()['test_setting:bool'].setter.assert_called_with(True)
        self.mqtt_client_mock.publish.assert_called_with('test_topic/test_setting/bool', 'True')

    def test_on_message_int(self):
        msg = MagicMock()
        msg.topic = 'test_topic/test_setting/int'
        msg.payload = b'20'

        self.miio_mqtt.client.on_message(self.mqtt_client_mock, self.miio_mqtt, msg)

        self.device_mock.settings()['test_setting:int'].setter.assert_called_with(20)
        self.mqtt_client_mock.publish.assert_called_with('test_topic/test_setting/int', '20')

    @patch('time.sleep', return_value=None)
    def test_connection_error(self, sleep_mock):
        self.mqtt_client_mock.reset_mock()
        self.mqtt_client_mock.connect.side_effect = [ConnectionError, None]
        self.miio_mqtt._connect()
        self.assertEqual(self.mqtt_client_mock.connect.call_count, 2)

    def test_on_connect_failure(self):
        self.mqtt_client_mock.reset_mock()
        self.miio_mqtt.client.on_connect(self.mqtt_client_mock, self.miio_mqtt, None, 1, None)
        self.mqtt_client_mock.subscribe.assert_not_called()

    @patch('time.sleep', return_value=None)
    def test_on_disconnect(self, sleep_mock):
        self.mqtt_client_mock.reset_mock()
        self.mqtt_client_mock.reconnect.side_effect = [Exception, None]
        self.miio_mqtt.client.on_disconnect(self.miio_mqtt, 1, None, None)
        self.assertEqual(self.mqtt_client_mock.reconnect.call_count, 2)

    def test_on_disconnect_none(self):
        self.mqtt_client_mock.reset_mock()
        self.miio_mqtt.client.on_disconnect(self.miio_mqtt, None, None, None)
        self.mqtt_client_mock.reconnect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
