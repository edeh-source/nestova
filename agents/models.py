from django.db import models
from django.contrib.auth import get_user_model
import random
import string



User = get_user_model()


class Bank(models.Model):
    """Nigerian Banks"""
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=10, unique=True)  # Bank code for API integrations
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name



class Agent(models.Model):
    """
    Agent Profile Linked To User

    Args:
        models (_type_): _description_
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agent_profile')
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    upline = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='downlines')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.00)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    facebook_page = models.URLField(blank=True, null=True)
    linkedin_page = models.URLField(blank=True, null=True)
    instagram_page = models.URLField(blank=True, null=True)
    x_page = models.URLField(blank=True, null=True)
    bank = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=10, blank=True)
    bank_verified = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True)
    
    
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)
        
        
    def generate_referral_code(self):
        """
        Generate unique 8-digit referral code
        """ 
        while True:
            code = ''.join(random.choices(string.digits, k=8))
            if not Agent.objects.filter(referral_code=code).exists():
                return code
            
    def __str__(self):
        return f"{self.user.username}"       
    
    
    
    def is_agent(user):
        """
        check if user has agent profile
        """    
        return hasattr(user, 'agent_profile')
    
    def get_total_commission(self):
        """Get total approved commissions for this agent"""
        from decimal import Decimal
        total = self.commissions.filter(status='approved').aggregate(
            total=models.Sum('commission_amount')
        )['total']
        return total or Decimal('0.00')
    
    def get_pending_commission(self):
        """Get total pending commissions"""
        from decimal import Decimal
        total = self.commissions.filter(status='pending').aggregate(
            total=models.Sum('commission_amount')
        )['total']
        return total or Decimal('0.00')
    
    def get_paid_commission(self):
        """Get total paid commissions"""
        from decimal import Decimal
        total = self.commissions.filter(status='paid').aggregate(
            total=models.Sum('commission_amount')
        )['total']
        return total or Decimal('0.00')
    
    
    def get_approved_commission(self):
        """Get total paid commissions"""
        from decimal import Decimal
        total = self.commissions.filter(status='approved').aggregate(
            total=models.Sum('commission_amount')
        )['total']
        return total or Decimal('0.00')
    
    def get_downline_count(self):
        """Get count of direct downlines"""
        return self.downlines.filter(is_active=True).count()


class PropertySale(models.Model):
    """Track property sales for commission calculation"""
    from property.models import Property
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    property = models.ForeignKey('property.Property', on_delete=models.CASCADE, related_name='sales')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='property_purchases')
    referring_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_sales')
    
    sale_price = models.DecimalField(max_digits=15, decimal_places=2)
    sale_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment tracking
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_reference = models.CharField(max_length=200, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Property Sale'
        verbose_name_plural = 'Property Sales'
    
    def __str__(self):
        return f"Sale: {self.property.title} - {self.buyer.username}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Auto-create commission if there's a referring agent and sale is completed
        if is_new and self.referring_agent and self.status == 'completed':
            self.create_commission()
    
    def create_commission(self):
        """Create commission record for referring agent"""
        if not self.referring_agent:
            return None
        
        commission_amount = self.sale_price * (self.referring_agent.commission_rate / 100)
        
        commission, created = Commission.objects.get_or_create(
            sale=self,
            agent=self.referring_agent,
            defaults={
                'commission_amount': commission_amount,
                'commission_rate': self.referring_agent.commission_rate,
                'status': 'pending'
            }
        )
        return commission


class Commission(models.Model):
    """Track commission earnings for agents"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]
    
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='commissions')
    sale = models.ForeignKey(PropertySale, on_delete=models.CASCADE, related_name='commissions')
    
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Rate at time of sale")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Approval tracking
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_commissions')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Payment tracking
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=200, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    
    # Notes
    admin_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Commission'
        verbose_name_plural = 'Commissions'
    
    def __str__(self):
        return f"Commission: {self.agent.user.username} - ₦{self.commission_amount:,.2f}"
    
    def approve(self, approved_by_user):
        """Approve commission"""
        from django.utils import timezone
        self.status = 'approved'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()
    
    def mark_as_paid(self, payment_reference='', payment_method=''):
        """Mark commission as paid"""
        from django.utils import timezone
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.payment_reference = payment_reference
        self.payment_method = payment_method
        self.save()
    
    def reject(self, reason=''):
        """Reject commission"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.save()