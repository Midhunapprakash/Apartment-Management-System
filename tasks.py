from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from .models import AmenityBooking

def expire_old_bookings():
    today = timezone.now().date()

    one_day_expired = AmenityBooking.objects.filter(
        amenity__booking_duration='1d',
        booking_status__in=['Pending', 'Approved'],
        booking_date__lte=today - timedelta(days=1)
    )

    one_month_expired = AmenityBooking.objects.filter(
        amenity__booking_duration='1m',
        booking_status__in=['Pending', 'Approved'],
        booking_date__lte=today - relativedelta(months=1)
    )

    one_day_expired.update(booking_status='Expired')
    one_month_expired.update(booking_status='Expired')