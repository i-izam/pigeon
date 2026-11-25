from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('welcome/', views.splash, name='splash'),
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('chat/<str:username>/', views.chat_room, name='chat_room'),
    path('groups/new/', views.create_group, name='create_group'),
    path('group/<int:group_id>/', views.group_room, name='group_room'),
]