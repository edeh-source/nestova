# users/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Handle phone_number for social logins
        """
        # If user doesn't exist yet, this will be called before creating
        if not sociallogin.is_existing:
            # Set phone_number to None for social logins
            if hasattr(sociallogin.user, 'phone_number'):
                sociallogin.user.phone_number = None
    
    def save_user(self, request, sociallogin, form=None):
        """
        Saves a newly created social login user.
        """
        user = super().save_user(request, sociallogin, form)
        # Ensure phone_number is None for social signups
        if user.phone_number == '':
            user.phone_number = None
            user.save()
        return user