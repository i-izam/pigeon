from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Message, ChatGroup, GroupMessage


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Presence", {"fields": ("last_seen",)}),
    )


admin.site.register(User, CustomUserAdmin)
admin.site.register(Message)
admin.site.register(ChatGroup)
admin.site.register(GroupMessage)