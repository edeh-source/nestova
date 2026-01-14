from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'phone_number', 'first_name', 'last_name', 'is_active', 'is_staff', 'created', 'updated']
    list_filter = ['username', 'email', 'phone_number', 'first_name', 'last_name', 'is_active', 'is_staff', 'created', 'updated']