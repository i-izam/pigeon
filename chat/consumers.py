import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Message, User


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        other_username = self.scope['url_route']['kwargs']['username']
        self.other = await self.get_user(other_username)
        if self.other is None:
            await self.close()
            return

        a, b = sorted([self.user.id, self.other.id])
        self.room_group_name = f'chat_{a}_{b}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        print(f'[WS] CONNECT user={self.user.username} other={self.other.username} group={self.room_group_name}')
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        text = data.get('message', '').strip()
        if not text:
            print(f'[WS] RECEIVE from={self.user.username} to={self.other.username} text={text}')
            return

        await self.save_message(text)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': text,
                'sender': self.user.username,
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
        }))

    @database_sync_to_async
    def get_user(self, username):
        return User.objects.filter(username=username).first()

    @database_sync_to_async
    def save_message(self, text):
        Message.objects.create(sender=self.user, receiver=self.other, text=text)