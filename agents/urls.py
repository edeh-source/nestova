from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    path('dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path("agents/signup/", views.agents_signup, name="agents_signup"),
    
    # Verification URLs
    path('verification/', views.verification_dashboard, name='verification_dashboard'),
    path('verification/submit/agent/', views.submit_agent_verification, name='submit_agent_verification'),
    path('verification/submit/company/', views.submit_company_verification, name='submit_company_verification'),
]

