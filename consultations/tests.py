from unittest import TestCase
from channels.testing import WebsocketCommunicator
from .consumers import ChatConsumer


class ChatConsumerTests(TestCase):
    async def test_connect(self):
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(), "/ws/conversation/1/"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()