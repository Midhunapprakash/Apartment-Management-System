import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):

    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('resident', 'Resident'),
        ('security', 'Security'),
        ('maintenance', 'Maintenance'),
    )
    phone = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='resident'
    )

    status = models.CharField(
        max_length=10,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('blocked', 'Blocked')
        ],
        default='inactive'
    )
    owner_status = models.CharField(max_length=20, choices=[('none','None'),('pending','Pending Payment'),('active','Active Owner')], default='0')
    def __str__(self):
        return f"{self.username} ({self.role})"

class Flat(models.Model):

    STATUS_CHOICES = (
        ('sale', 'For Sale'),
        ('rent', 'For Rent'),
    )

    BHK_CHOICES = (
        ('1bhk', '1 BHK'),
        ('2bhk', '2 BHK'),
        ('3bhk', '3 BHK'),
        ('4bhk', '4 BHK'),
    )
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    flat_number = models.CharField(max_length=20, unique=True)
    furnished = models.CharField(max_length=2, default='FF', choices=[('FF', 'Fully Furnished'), ('SF', 'Semi-Furnished')])
    description = models.TextField()
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    maintenance_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    block= models.CharField(max_length=50,null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sale')
    bhk_type = models.CharField(max_length=10, choices=BHK_CHOICES)
    bedrooms = models.PositiveIntegerField()
    bathrooms = models.PositiveIntegerField()
    floor_number = models.PositiveIntegerField()
    built_up_area = models.PositiveIntegerField()
    is_available = models.BooleanField(default=True)
    flat_image = models.ImageField(upload_to='flats/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.flat_number
        
class FlatImage(models.Model):
    flat = models.ForeignKey(Flat, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(max_length=300)

class ResidentProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    proof_verified = models.BooleanField(default=False)
    flat = models.ForeignKey(
        Flat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="residents"
    )

    owned_by = models.CharField(max_length=12, default='admin')

    is_approved = models.BooleanField(default=False)

    aadhaar = models.CharField(max_length=255, null=True, blank=True ,default="Not Provided")
    photo = models.CharField(max_length=255, null=True, blank=True,default="Not Provided")

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.flat}"


class StaffWorkLog(models.Model):

    WORK_STATUS = (
        ('not_started', 'Not Started'),
        ('completed', 'Completed'),
        ('reassigned', 'Reassigned'),
        ('inprogress', 'In Progress'),
    )


    # Date of work
    date = models.DateField(default=timezone.now)

    # Assigned staff
    assigned_staff = models.ForeignKey(
        'StaffProfile', 
        on_delete=models.CASCADE
    )

    # Work details
    work_status = models.CharField(
        max_length=20,
        choices=WORK_STATUS,
        default='not_started'
    )


    # Resident confirms work
    resident_confirmation = models.BooleanField(default=False)

    # Time tracking (filled by staff)
    started_time = models.DateTimeField(null=True, blank=True)
    ending_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.assigned_staff.user.first_name} - {self.work_status}"

class StaffRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    image = models.CharField(max_length=255, blank=True, null=True)
    def __str__(self):
        return self.name

class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.ForeignKey(StaffRole, on_delete=models.CASCADE, null=True, blank=True)

class Visitor(models.Model):
    visitor_name = models.CharField(max_length=100)
    purpose = models.CharField(max_length=200)

    entry_time = models.DateTimeField(null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    image = models.CharField(max_length=255, blank=True, null=True ,default="Not Provided")
    registered_by = models.ForeignKey(
        StaffProfile, on_delete=models.SET_NULL,
        null=True, blank=True
    )

    resident = models.ForeignKey(
        ResidentProfile, on_delete=models.CASCADE
    )

    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending','Pending'),
            ('approved','Approved'),
            ('rejected','Rejected'),
            ('entered','Entered'),
            ('exited','Exited')
        ],
        default='pending'
    )

# models.py
class Complaint(models.Model):
    COMPLAINT_TYPE = (
        ('maintenance', 'Maintenance'),
        ('service', 'Service'),
    )

    STATUS = (
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    )

    resident = models.ForeignKey(User, on_delete=models.CASCADE)
    issue = models.CharField(max_length=200,null=True)
    complaint_type = models.CharField(max_length=20, choices=COMPLAINT_TYPE,null=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    admin_response = models.TextField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    urgent = models.BooleanField(default=False)

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()

class Parcel(models.Model):
    resident = models.ForeignKey(ResidentProfile, on_delete=models.CASCADE)
    courier_name = models.CharField(max_length=100)
    received_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[('received','Received'),('collected','Collected')],
        default='received'
    )

class StaffEntryLog(models.Model):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE)
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('inside','Inside'),('exited','Exited')],
        default='inside'
    )

    def __str__(self):
        return self.staff.user.first_name + " - " + self.status


class Amenity(models.Model):
    BOOKING_DURATION_CHOICES = [
        ('1d', '1 Day'),
        ('1m', '1 Month'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.CharField(max_length=255, blank=True, null=True)
    is_bookable = models.BooleanField(default=True)
    charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    max_people = models.PositiveIntegerField()

    booking_duration = models.CharField(
        max_length=2,
        choices=BOOKING_DURATION_CHOICES,
        default='1d'
    )
    created_at = models.DateTimeField(auto_now_add=True,null=True)

    status = models.CharField(max_length=20, choices=[
        ('Active', 'Active'),
        ('Inactive', 'Inactive')
    ], default='Active')

class AmenityTimeSlot(models.Model):
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.amenity.name} ({self.start_time} - {self.end_time})"

class AmenityOffDay(models.Model):
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]

    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAY_CHOICES)

    def __str__(self):
        return f"{self.amenity.name} - {self.day}"

class AmenityBooking(models.Model):
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE)
    resident = models.ForeignKey(User, on_delete=models.CASCADE)
    booking_date = models.DateField()
    time_slot = models.ForeignKey(AmenityTimeSlot, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=[
        ('Paid', 'Paid'),
        ('Unpaid', 'Unpaid')
    ], default='Unpaid')
    booking_status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
        ('Expired', 'Expired')
    ], default='Pending')

    created_at = models.DateTimeField(auto_now_add=True,null=True)

    def __str__(self):
        return f"{self.amenity.name} - {self.resident.username}"

class AmenityPayment(models.Model):
    booking = models.ForeignKey(AmenityBooking, on_delete=models.CASCADE)
    resident = models.ForeignKey(User, on_delete=models.CASCADE)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_mode = models.CharField(max_length=50,default="online")
    status = models.CharField(max_length=20,default="Success", choices=[
        ('Success', 'Success'),
        ('Failed', 'Failed')
    ])

    def __str__(self):
        return f"{self.resident.username} - {self.booking.amount}"

class FlatAllocation(models.Model):
    flat = models.ForeignKey(Flat, on_delete=models.CASCADE)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_flats"
    )

    current_resident = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="occupied_flats"
    )

    ALLOCATION_TYPE = (
        ('self', 'Owner Living'),
        ('rent', 'Rented'),
    )

    allocation_type = models.CharField(max_length=20, choices=ALLOCATION_TYPE)

    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)


class VacateRequest(models.Model):
    resident = models.ForeignKey(User, on_delete=models.CASCADE)
    flat = models.ForeignKey(Flat, on_delete=models.CASCADE)
    allocation = models.ForeignKey(FlatAllocation, on_delete=models.CASCADE)

    request_date = models.DateField(auto_now_add=True)

    STATUS = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(max_length=20, choices=STATUS, default='pending')

    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment =  models.ForeignKey('Payment', on_delete=models.CASCADE,default=1)

    def __str__(self):
        return f"{self.resident.username} - Vacate Request"

class Payment(models.Model):
    resident = models.ForeignKey('ResidentProfile', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[('paid','Paid'),('pending','Pending')],
        default='pending'
    )
    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    # Link to Receipt
    receipt = models.OneToOneField('Receipt', on_delete=models.SET_NULL, null=True, blank=True)

    receipt_no = models.CharField(max_length=50, unique=True, blank=True)
    paid_to = models.ForeignKey('User',null=True, on_delete=models.CASCADE,)

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            self.receipt_no = "APT-" + uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.resident.user.first_name} - {self.amount} ({self.status})"

class OwnerPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owner_payments')
    flat = models.ForeignKey('Flat', on_delete=models.CASCADE)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('paid', 'Paid')
    ], default='pending')

    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    # Link to Receipt
    receipt = models.OneToOneField('Receipt', on_delete=models.SET_NULL, null=True, blank=True)

    receipt_no = models.CharField(max_length=50, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-generate receipt number if not set
        if not self.receipt_no:
            self.receipt_no = "OWNER-" + uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.first_name} - {self.flat.flat_number} ({self.status})"


class Receipt(models.Model):
    receipt_no = models.CharField(max_length=50, unique=True)
    file_path = models.CharField(max_length=255)  # relative path in static
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Receipt - {self.receipt_no}"


class CommunityChat(models.Model):
    resident = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    # Add this field for replies
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        
    def __str__(self):
        return f"{self.resident.username}: {self.message[:20]}"

class SupportRequest(models.Model):
    resident = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending','Pending'),
            ('assigned','Assigned'),
            ('completed','Completed')
        ],
        default='pending'
    )
    task = models.ForeignKey(
        StaffWorkLog,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    urgent = models.BooleanField(default=False)

class Notice(models.Model):

    PRIORITY_CHOICES = (
        ('normal', 'Normal'),
        ('important', 'Important'),
        ('emergency', 'Emergency'),
    )

    TARGET_CHOICES = (
        ('all', 'All Users'),
        ('resident', 'Residents'),
        ('security', 'Security'),
        ('maintenance', 'Maintenance'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('expired', 'Expired'),
    )

    title = models.CharField(max_length=200)
    message = models.TextField()

    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")

    target_role = models.CharField(max_length=20, choices=TARGET_CHOICES, default="all")

    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    valid_until = models.DateField()

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")

    def save(self, *args, **kwargs):
        if self.valid_until.date() < timezone.now().date():
            self.status = "expired"
        else:
            self.status = "active"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

