from django.urls import path
from . import views


urlpatterns = [
    path('dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path("agents/signup/", views.agents_signup, name="agents_signup"),
]
