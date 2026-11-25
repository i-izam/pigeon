import json

from django.db.models import Count
from django.utils import timezone
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ChatGroup, GroupMessage, Message, User

# user_id -> kitne sockets/tabs connected hain (dev ke liye in-memory)
ONLINE = {}


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

        # typing event: database mein save nahi hota, bas forward hota hai
        if data.get('type') == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_status',
                    'sender': self.user.username,
                    'is_typing': bool(data.get('is_typing')),
                },
            )
            return

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

            # sender ko batao ki message dekh liya gaya (✓✓)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'messages_read',
                    'reader': self.user.username,
                },
            )

            # Update unread count for the current user
            await self.channel_layer.group_send(
                f'notifications_{self.user.id}',
                {'type': 'unread_update'}
            )

        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
        }))

    async def messages_read(self, event):
        # jisne padha usko ye event wapas mat bhejo
        if event['reader'] == self.user.username:
            return

        await self.send(text_data=json.dumps({
            'type': 'read',
            'reader': event['reader'],
        }))

    async def typing_status(self, event):
        # apna typing event khud ko wapas mat bhejo
        if event['sender'] == self.user.username:
            return

        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender': event['sender'],
            'is_typing': event['is_typing'],
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


class GroupChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_id = self.scope['url_route']['kwargs']['group_id']

        # sirf group ke members hi connect kar sakte hain
        if not await self.is_member():
            await self.close()
            return

        self.group_name = f'group_{self.group_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        text = data.get('message', '').strip()

        if not text:
            return

        msg = await self.save_group_message(text)
        sent_time = timezone.localtime(msg.timestamp).strftime('%H:%M')

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'group_message',
                'message': text,
                'sender': self.user.username,
                'time': sent_time,
            },
        )

    async def group_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'time': event['time'],
        }))

    @database_sync_to_async
    def is_member(self):
        return ChatGroup.objects.filter(
            id=self.group_id,
            members=self.user
        ).exists()

    @database_sync_to_async
    def save_group_message(self, text):
        return GroupMessage.objects.create(
            group_id=self.group_id,
            sender=self.user,
            text=text
        )


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


class PresenceConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add('presence', self.channel_name)
        await self.accept()

        ONLINE[self.user.id] = ONLINE.get(self.user.id, 0) + 1

        # is naye socket ko abhi kaun online hai, wo bhej do
        await self.send(text_data=json.dumps({
            'type': 'initial',
            'online': list(ONLINE.keys()),
        }))

        # agar yeh user ka pehla socket hai, sabko batao ki wo online aaya
        if ONLINE[self.user.id] == 1:
            await self.channel_layer.group_send('presence', {
                'type': 'presence_update',
                'user_id': self.user.id,
                'online': True,
            })

    async def disconnect(self, close_code):
        if not hasattr(self, 'user') or not self.user.is_authenticated:
            return

        await self.channel_layer.group_discard('presence', self.channel_name)

        ONLINE[self.user.id] = ONLINE.get(self.user.id, 1) - 1

        if ONLINE[self.user.id] <= 0:
            ONLINE.pop(self.user.id, None)
            await self.save_last_seen()
            await self.channel_layer.group_send('presence', {
                'type': 'presence_update',
                'user_id': self.user.id,
                'online': False,
            })

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'update',
            'user_id': event['user_id'],
            'online': event['online'],
        }))

    @database_sync_to_async
    def save_last_seen(self):
        User.objects.filter(id=self.user.id).update(last_seen=timezone.now())