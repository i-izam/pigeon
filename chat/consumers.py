
import json

from django.db.models import Count
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

        if self.other is None or self.other.id == self.user.id:
            await self.close()
            return

        a, b = sorted([self.user.id, self.other.id])
        self.room_group_name = f'chat_{a}_{b}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        text = data.get('message', '').strip()

        if not text:
            return

        msg = await self.save_message(text)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'id': msg.id,
                'message': text,
                'sender': self.user.username,
            },
        )

        # Notify receiver about unread message
        await self.channel_layer.group_send(
            f'notifications_{self.other.id}',
            {'type': 'unread_update'}
        )

    async def chat_message(self, event):
        if event['sender'] != self.user.username:
            await self.mark_read(event['id'])

            # Update unread count for the current user
            await self.channel_layer.group_send(
                f'notifications_{self.user.id}',
                {'type': 'unread_update'}
            )

        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
        }))

    @database_sync_to_async
    def get_user(self, username):
        return User.objects.filter(username=username).first()

    @database_sync_to_async
    def save_message(self, text):
        return Message.objects.create(
            sender=self.user,
            receiver=self.other,
            text=text
        )

    @database_sync_to_async
    def mark_read(self, message_id):
        Message.objects.filter(
            id=message_id,
            receiver=self.user
        ).update(is_read=True)


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f'notifications_{self.user.id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # Send initial unread counts
        await self.send_unread_counts()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def unread_update(self, event):
        await self.send_unread_counts()

    async def send_unread_counts(self):
        counts = await self.get_unread_counts()

        await self.send(text_data=json.dumps({
            'type': 'unread_update',
            'counts': counts
        }))

    @database_sync_to_async
    def get_unread_counts(self):
        return dict(
            Message.objects.filter(
                receiver=self.user,
                is_read=False
            )
            .values('sender_id')
            .annotate(total=Count('id'))
            .values_list('sender_id', 'total')
        )
