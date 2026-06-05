from apartment_app.models import User   # change to your actual User model
from .models import *
def logged_user(request):
    user = None
    flat = None
    count = None
    user_id = request.session.get("log_id")

    if user_id:
        try:
            count=FlatAllocation.objects.filter(owner_id=user_id,is_active=1).count()
            print(count)
            user = User.objects.get(id=user_id)
            if(user.role == 'resident'):
                resident = ResidentProfile.objects.get(user_id=user_id)
                if resident.is_approved == 1:
                    flat=request.session.get('flat') 
            if(count > 0):
                count=count
        except User.DoesNotExist:
            pass

    return {
        "logged_user": user,
        "flat":flat,
        "count":count
    }
