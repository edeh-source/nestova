from django.shortcuts import render, redirect
from .models import Agent
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth import login
from .models import Bank
from django.http import JsonResponse
from .models import Agent
from django.contrib import messages
from django.urls import reverse


User = get_user_model()


# Helper function to use in views
def agent_required(view_func):
    """Decorator to ensure user is an agent"""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'agent_profile'):
            messages.error(request, 'You must be an agent to access this page')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper

# Usage:
from django.contrib.auth.decorators import login_required

@login_required
@agent_required
def agent_dashboard(request):
    """Only agents can access this"""
    agent = request.user.agent_profile
    return render(request, 'agents/dashboard.html', {'agent': agent})


def agents_signup(request):
    """
    A method to signup for an agent
    """
    if not request.user.is_authenticated:
        messages.info(request, "You Must Have An Account Before You Can Become An Agent")
        return redirect("login")
    if Agent.objects.filter(user=request.user).exists():
        return redirect('shop:profile')
    else:
        banks = Bank.objects.all()
        if request.method == "POST":
            bank_id = request.POST.get("bank")
            account_name = request.POST.get('account_name')
            account_number = request.POST.get('account_number')
            upline_code = request.POST.get('upline_code') or request.GET.get('ref')
            upline = None 
            if upline_code:
                try:
                    upline = Agent.objects.get(referral_code=upline_code)
                except Agent.DoesNotExist:
                    messages.warning(request, 'Invalid referral code, registered without upline')
                    
            if bank_id:
                try:
                    bank = Bank.objects.get(id=bank_id)
                except Bank.DoesNotExist:
                    pass
                
            agent = Agent.objects.create(user=request.user, upline=upline, bank=bank, account_name=account_name, account_number=account_number, bank_verified=False)
            try:
                user = User.objects.get(username=agent.user.username)
                user.is_agent = True
                user.save()
            except User.DoesNotExist:
                return JsonResponse({
                    "status": "error",
                    "message": "User Does Not Exist"
                })    
            return JsonResponse({
                "status": "success",
                "message": "Agent Profile Created Successfully",
                "redirect_url": reverse("shop:profile")
            })
        else:
            upline_code = request.GET.get('ref')
            print("This is the upline code", upline_code)
            upline_agent = None
            if upline_code:
                try:
                    upline_agent = Agent.objects.get(referral_code=upline_code)
                    print("There is an upline agent", upline_agent)
                except Agent.DoesNotExist:
                    print("There is no agent with such referral code")
                    upline_agent = None
            return render(request, "agents/signup.html", {"banks": banks, 'upline_code': upline_code, 'upline_agent': upline_agent,})

            
                       
    


# views.py


