from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path(
        'ws/chat/<str:username>/',
        consumers.ChatConsumer.as_asgi()
    ),
    path(
        'ws/group/<int:group_id>/',
        consumers.GroupChatConsumer.as_asgi()
    ),
    path(
        'ws/notifications/',
        consumers.NotificationConsumer.as_asgi()
    ),
    path(
        'ws/presence/',
        consumers.PresenceConsumer.as_asgi()
    ),
]