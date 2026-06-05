from django.conf import settings
from .models import *
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login as auth_login,logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum, Count
from django.apps import apps
from django.shortcuts import render, get_object_or_404, redirect
from datetime import date
from django.template.loader import render_to_string
from xhtml2pdf import pisa
import os, uuid,csv,calendar
from django.utils.timezone import now
from django.utils import timezone
from datetime import datetime
from django.db.models import Q
from django.db.models import Sum, F, Count
import random
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.apps import apps
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def home(request):
    try:
        expire_old_bookings()
    except:
        if(request.session.get("role")):
            return redirect('dashboard')
        # Get all available flats (you can limit number for featured)
    flats = Flat.objects.filter(is_available=True).order_by('-created_at')[:6]
    roles = StaffRole.objects.all()
    context = {
        'flats': flats,
        'roles': roles,
    }

    return render(request, 'home/index.html', context)

def add_admin(request):
    obj=User.objects.filter(role = 'admin').count()
    if(obj == 0):
        user = User.objects.create_user(
            username="admin",
            first_name='Shaine',
            last_name='Shinoj',
            email="admin@mail.com",
            password="admin@123",
            phone="9980786755",
            role='admin',
            is_active=1,
            status='active',
            owner_status=0
        )
        return redirect('home')
    else:
        return redirect('home')

def login(request):
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # 1. Authenticate the user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            request.session['log_id'] = user.id
            request.session['role'] = getattr(user, 'role', None) # Safely get role
            # Check for Inactive Status first
            if user.status == 'inactive':
                if user.owner_status == '1':
                    return redirect('owner_payment')
                else:
                    messages.error(request, 'Your account is inactive. Please contact admin.')
                    return render(request, 'home/login.html')

            # 2. Log the user in officially
            auth_login(request, user)
            
            # 3. Set custom session variables
           

            # 4. Role-based Logic
            if user.role == 'resident':
                try:
                    resident = ResidentProfile.objects.get(user=user)
                    
                    # Check Payment Status if Owner
                    if user.owner_status == '1':
                        payment = OwnerPayment.objects.filter(user=user).first()
                        if payment and payment.status == 'pending':
                            return redirect("owner_payment")
                    
                    request.session['flat'] = resident.flat_id
                except ResidentProfile.DoesNotExist:
                    messages.error(request, "Resident profile not found.")
            
            return redirect('dashboard')

        else:
            # 5. Handle Failed Authentication
            user_exists = User.objects.filter(username=username).exists()
            if user_exists:
                existing_user = User.objects.get(username=username)
                if existing_user.status == 'inactive':
                    messages.error(request, 'Your account is inactive.')
                else:
                    messages.error(request, 'Invalid password.')
            else:
                return render(request, 'no_data.html')
                
    return render(request, 'home/login.html')

def amenity_booking_history(request):
    history=AmenityBooking.objects.filter(payment_status="Paid")
    return render(request, 'admin/amenity_booking_history.html',{'history':history})

def guest_view_flats(request):
    flats=Flat.objects.filter(is_available=1)
    return render(request, 'home/flats.html',{'flats':flats})

def guest_flat_details(request,id):
    flat = get_object_or_404(Flat, id =id)
    return render(request, 'home/flat_details.html',{'flat':flat})
    
def admin_flat_details(request, id):
    flat = get_object_or_404(Flat, id=id)

    return render(request, "admin/flat_details.html", {
        "flat": flat
    })

def delete_flat_image(request, image_id):
    img = FlatImage.objects.get(id=image_id)
    flat_id = img.flat.id
    img.delete()
    messages.success(request, "Image removed")
    return redirect("admin_flat_gallery", flat_id)


def admin_flat_gallery(request, flat_id):
    flat = Flat.objects.get(id=flat_id)
    images = FlatImage.objects.filter(flat=flat)

    if request.method == "POST":
        files = request.FILES.getlist("images")

        app_path = apps.get_app_config('apartment_app').path
        upload_dir = os.path.join(app_path, 'static', 'uploads', 'flat_images')
        os.makedirs(upload_dir, exist_ok=True)

        for file in files:
            file_name = file.name.replace(" ", "_")
            full_path = os.path.join(upload_dir, file_name)

            # Save file physically
            with open(full_path, "wb+") as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            # Save relative path in DB
            FlatImage.objects.create(
                flat=flat,
                image=f"uploads/flat_images/{file_name}"
            )

        messages.success(request, "Images uploaded successfully")
        return redirect("admin_flat_gallery", flat_id=flat.id)

    return render(request, "admin/flat_gallery.html", {
        "flat": flat,
        "images": images
    })

def owner_payment(request):

    user_id = request.session.get("log_id")
    resident=ResidentProfile.objects.get(user_id=user_id)

    if not user_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect("login")

    user = get_object_or_404(User, id=user_id)
    try:
        payment = OwnerPayment.objects.get(user=user, status="pending")
    except OwnerPayment.DoesNotExist:
        if(resident.is_approved == 1):
            return redirect("dashboard")
        else:
            messages.success(request, "Payment successful! Just be patient our admin go ahead with approval soon ..")
            return render(request,"home/login.html")

    if request.method == "POST":
        # ----------------- Mark payment as paid -----------------
        payment.paid_amount = payment.total_amount
        payment.status = "paid"
        payment.transaction_id = "TXN" + uuid.uuid4().hex[:10].upper()
        payment.save()

        # ----------------- Update user to active owner -----------------
        user.owner_status = "1"
        # user.status = "active"
        user.save()

        # ----------------- Assign flat ownership -----------------
        flat = payment.flat
        flat.owner = user
        flat.is_available = False
        flat.save()


        # ----------------- Generate PDF receipt -----------------
        receipt_html = render_to_string(
            'resident/owner_receipt_template.html',
            {'payment': payment, 'user': user, 'flat': flat}
        )

        # Ensure folder exists
        app_path = apps.get_app_config('apartment_app').path
        upload_dir = os.path.join(app_path, 'static', 'uploads', 'receipts')
        os.makedirs(upload_dir, exist_ok=True)

        receipt_filename = f"OWNER_{payment.id}.pdf"
        receipt_path = os.path.join(upload_dir, receipt_filename)

        # Generate PDF
        pdf_created = False
        try:
            with open(receipt_path, "wb") as f:
                pisa_status = pisa.CreatePDF(receipt_html, dest=f)
            pdf_created = not pisa_status.err
        except Exception as e:
            messages.warning(request, f"Payment successful but failed to generate PDF: {str(e)}")

        if pdf_created:
            # ----------------- Save Receipt in DB -----------------
            receipt = Receipt.objects.create(
                receipt_no=f"OWNER-{payment.id}",
                file_path=f"uploads/receipts/{receipt_filename}"
            )
            receipt_id=Receipt.objects.get(id=receipt.id)
            # ----------------- Link receipt to OwnerPayment -----------------
            payment.receipt = receipt_id
            payment.save()  # <-- THIS ensures receipt_id is saved
        else:
            messages.warning(request, "Payment successful but receipt not saved due to PDF error.")

        messages.success(request, "Payment successful! Receipt generated and saved.")
        if(resident.is_approved == 1):
            return redirect("dashboard")
        else:
            return render(request,"home/login.html")

    return render(request, "home/payment.html", {"payment": payment})

@login_required
def dashboard(request):
    role = request.session.get('role')
    user_id = request.session.get('log_id')
    user = User.objects.get(id=user_id)
    
    # Notifications for logged-in user
    notifications = Notification.objects.filter(
        user_id=user_id,is_read=0
    ).order_by("-created_at")[:10]

    unread_count = Notification.objects.filter(
        user_id=user_id,
        is_read=False
    ).count()

    # Admin data
    resident = ResidentProfile.objects.filter(user__status = 'active')
    flats = Flat.objects.all()
    complaints = Complaint.objects.filter(status='pending').count()
    req = SupportRequest.objects.filter(status='pending').count()

    if role == 'admin':
        return render(request, 'admin/admin_dashboard.html', {
            'resident': resident,
            'flats': flats,
            'complaints': complaints,
            'req': req,
            'user': user,
            'notifications': notifications,
            'unread_count': unread_count
        })

    elif role == 'resident':
        bills = Payment.objects.filter(
            resident__user=user_id,
            status='pending'
        )

        return render(request, 'resident/index.html', {
            'bill': bills,
            'complaints': complaints,
            'req': req,
            'user': user,
            'notifications': notifications,
            'unread_count': unread_count
        })

    elif role == 'staff':
        return redirect('staff_dashboard')

    elif role == 'security':
        return redirect('security_dashboard')

    else:
        return redirect('home')

def mark_notification_read(request, id):
    n = Notification.objects.get(id=id)
    n.is_read = True
    n.save()
    return redirect(request.META.get("HTTP_REFERER"))
@login_required

def staff_dashboard(request):
    flat=flat=Flat.objects.all()
    user = User.objects.get(id=request.session['log_id'])
    staff = StaffProfile.objects.get(user=user)
    role = staff.role.name.lower()   # plumber / electrician / etc
    resident=ResidentProfile.objects.all()
    tasks=SupportRequest.objects.filter(task__assigned_staff__user__id=request.session.get('log_id'),status='assigned',task__work_status__in=['completed'])
    return render(request, 'staff/index.html', {
        'tasks': tasks,
        'staff_role': role,
        'staff': staff,
        'resident':resident,
        'flats':flat,
        'user':user
    })
@login_required

def security_dashboard(request):
    flat=flat=Flat.objects.all()
    user = User.objects.get(id=request.session['log_id'])
    staff = StaffProfile.objects.get(user=user)
    role = staff.role.name.lower()   # plumber / electrician / etc
    resident=ResidentProfile.objects.all()
    tasks=SupportRequest.objects.filter(task__assigned_staff__user__id=request.session.get('log_id'),status='assigned',task__work_status__in=['completed'])
    return render(request, 'security/index.html', {
        'tasks': tasks,
        'staff_role': role,
        'staff': staff,
        'resident':resident,
        'flats':flat,
        'user':user
    })

import os
import time
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

def account_exist(request):
    return render(request,'account_exist.html')

def register(request):

    selected_flat_id = request.POST.get('flat') or request.GET.get('flat_id')

    if not selected_flat_id:
        messages.error(request, "No flat selected.")
        return redirect('guest_view_flats')

    flat = get_object_or_404(Flat, id=selected_flat_id)

    if request.method == "POST":

        # -------- ROLE CHECK --------
        role = '1' if flat.status == 'sale' else '0'
       

        # -------- PASSWORD CHECK --------
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect(f'/register?flat_id={selected_flat_id}')

        email = request.POST.get('email')
        phone=request.POST.get('phone'),


        if User.objects.filter(email=email).exists():
            return redirect('account_exist')
        
        if User.objects.filter(phone=phone).exists():
            return redirect('account_exist')


        if not flat.is_available:
            # messages.error(request, "Flat already occupied")
            return redirect('guest_view_flats')

        # -------- FILE UPLOAD --------
        aadhaar_file = request.FILES.get('aadhaar')
        photo_file = request.FILES.get('photo')

        aadhaar_path = None
        photo_path = None

        upload_dir = os.path.join(settings.BASE_DIR, 'apartment_app', 'static', 'uploads', 'proofs')
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = str(int(time.time()))

        # Save Aadhaar
        # -------- SAVE AADHAAR --------
        if aadhaar_file:
            ext = os.path.splitext(aadhaar_file.name)[1]
            aadhaar_name = f"{uuid.uuid4().hex}{ext}"

            aadhaar_full_path = os.path.join(upload_dir, aadhaar_name)

            with open(aadhaar_full_path, 'wb+') as f:
                for chunk in aadhaar_file.chunks():
                    f.write(chunk)

            aadhaar_path = f"uploads/proofs/{aadhaar_name}"

        # Save Photo
        if photo_file:
            ext = os.path.splitext(photo_file.name)[1]
            photo_name = f"{uuid.uuid4().hex}{ext}"

            photo_full_path = os.path.join(upload_dir, photo_name)

            with open(photo_full_path, 'wb+') as f:
                for chunk in photo_file.chunks():
                    f.write(chunk)

            photo_path = f"uploads/proofs/{photo_name}"

        # -------- CREATE USER --------
        user = User.objects.create_user(
            username=request.POST.get('username'),
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            email=email,
            password=password,
            phone=phone,
            owner_status=role
        )

        # -------- RESIDENT PROFILE --------
        resident = ResidentProfile.objects.create(
            user=user,
            flat=flat,
            owned_by="admin",
            is_approved=False,
            aadhaar=aadhaar_path,
            photo=photo_path
        )

        # -------- AGREEMENT --------
        duration_days = int(request.POST.get("duration"))

        start_date_str = request.POST.get("start_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        end_date = start_date + timedelta(days=duration_days)

        admin = User.objects.filter(role='admin').first()

        FlatAllocation.objects.create(
            flat=flat,
            owner=admin,
            current_resident=user,
            allocation_type=flat.status,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )

        # -------- PAYMENT --------
        if user.owner_status =='1':

            payment = OwnerPayment.objects.create(
                user=user,
                flat=flat,
                total_amount=flat.purchase_price,
                status='pending'
            )
            

        else:

          payment =  Payment.objects.create(
                resident=resident,
                amount=flat.monthly_rent + flat.maintenance_charge,
                status='pending'
            )

        # -------- UPDATE FLAT --------
        flat.is_available = False
        flat.save()

        messages.success(request, "Registration successful. Waiting for admin approval.")

        return redirect("login")

    return render(request, "home/register.html", {
        "flat": flat,
        "selected_flat_id": selected_flat_id
    })

def reset_password(request):
    user_id = request.session.get('log_id')
    role = request.session.get('role')

    if not user_id:
        messages.error(request, "Unauthorized access")
        return redirect("login")

    user = User.objects.get(id=user_id)

    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        # 1️⃣ Check current password
        if not user.check_password(current_password):
            messages.error(request, "Current password is incorrect")
            return redirect("reset_password")

        # 2️⃣ Check new passwords match
        if new_password != confirm_password:
            messages.error(request, "New passwords do not match")
            return redirect("reset_password")

        # 3️⃣ Set new password
        user.set_password(new_password)
        user.save()

        # 4️⃣ Logout user after password change
        request.session.flush()

        messages.success(request, "Password updated successfully. Please login again.")
        return redirect("login")

    if role == "resident":
        return render(request, "resident/password_reset.html")
    elif role == "admin":
        return render(request, "admin/password_reset.html")
    elif role == "security":
        return render(request, "security/password_reset.html")
    else:
        return render(request, "staff/password_reset.html")

    return redirect("login")

def about(request):
    roles = StaffRole.objects.all()
    flats = Flat.objects.filter(is_available=True).order_by('-created_at')[:16]
    return render(request, 'home/about-us.html', {'flats': flats, 'roles': roles})

def contact(request):
    return render(request, 'home/contact.html')

def services(request):
    return render(request, 'home/services.html')
from django.http import JsonResponse
from django.db.models import Q

def global_search(request):
    q = request.GET.get("q", "")

    results = []

    if q:
        announcements = Announcement.objects.filter(title__icontains=q)[:5]
        for a in announcements:
            results.append({
                "title": a.title,
                "type": "Announcement",
                "url": "/announcement/"
            })

        notices = Notice.objects.filter(title__icontains=q)[:5]
        for n in notices:
            results.append({
                "title": n.title,
                "type": "Notice",
                "url": "/notices/"
            })

        visitors = Visitor.objects.filter(visitor_name__icontains=q)[:5]
        for v in visitors:
            results.append({
                "title": v.visitor_name,
                "type": "Visitor",
                "url": "/visitor-gate/"
            })

    return JsonResponse({"results": results})

def announcement(request):
    today = date.today()
    now = timezone.now()
    active_announce = Announcement.objects.all()
    announce = Announcement.objects.all().order_by('-created_at') 
    role = request.session.get('role')
    if role == 'admin':
        if request.method == "POST":
            announcement=Announcement.objects.create(
                title=request.POST.get("title"),
                message=request.POST.get("message"),
                valid_until=request.POST.get("valid_until")
            )
            users = User.objects.all()
            for user in users:
                Notification.objects.create(
                    user=user,
                    title="New Announcement",
                    message=announcement.title
                )

            return redirect('announcement')
        return render(request, 'admin/announcements.html', {'announcements': announce,'today':today})
    elif role == 'staff':
        return render(request, 'staff/announcement.html', {'announcements': announce,'today':today})
    elif role == 'security':
        return render(request, 'security/announcement.html', {'announcements': announce,'today':today})
    else:
        return render(request, 'resident/announcement.html', {'announcements': active_announce,'today':today})
    
def community(request):
    # if(request.session).get('role')=='donor':
    #     return render(request, 'donor/index.html')
    return render(request, 'resident/community.html') 

def make_owner(request, user_id, flat_id):
    user = User.objects.get(id=user_id)
    flat = Flat.objects.get(id=flat_id)

    # Create payment invoice
    OwnerPayment.objects.create(
        user=user,
        flat=flat,
        total_amount=flat.purchase_price
    )

    # DO NOT make owner yet
    user.owner_status = "0"
    user.save()

    messages.success(request, "Owner invoice created. User must complete payment to become owner.")
    return redirect("admin_residents")
    

def payment(request):
    role = request.session.get('role')
    user = User.objects.get(id=request.session.get('log_id'))

    # ADMIN
    if role == 'admin':
        payments = Payment.objects.filter(resident__owned_by = 'admin').order_by('-payment_date')
        owner_payments = OwnerPayment.objects.all().order_by('-created_at')
        return render(request, 'admin/payments.html', {'payments': payments,'owner_payments':owner_payments})

    # RESIDENT
    resident = ResidentProfile.objects.get(user=user)
    if(resident.owned_by == 'resident'):
        ref=FlatAllocation.objects.get(current_resident=user)
        recipient=User.objects.get(id=ref.owner_id)
    else:
        recipient=User.objects.get(role='admin')


    today = date.today()
    month = today.strftime("%b-%Y")   # Feb-2026
    # check if this month bill exists
    if resident.user.owner_status == '0' :
        if not Payment.objects.filter(resident=resident).exists():
            flat = resident.flat
            if(resident.owned_by == 'resident'):
                amount = flat.monthly_rent 
            else:
                amount = flat.monthly_rent + flat.maintenance_charge

            Payment.objects.create(
                resident=resident,
                amount=amount,
                status='pending',
                paid_to_id=recipient.id
            )
    if(user.owner_status == '1'):
        payments = OwnerPayment.objects.filter(user_id=user.id).order_by('-created_at')
    else:
        payments = Payment.objects.filter(resident=resident).order_by('-payment_date')

    return render(request, 'resident/payment.html', {'payments': payments})

def receipt_upload_path(instance, filename):
    return f"uploads/receipts/{filename}"

def make_payment(request, id,access):
    payment = Payment.objects.get(id=id)
    resident = payment.resident
    flat = resident.flat

    if request.method == "POST" and payment.status == "pending":
        # Mark payment as paid
        payment.status = "paid"
        payment.transaction_id = "TXN" + uuid.uuid4().hex[:10].upper()
        if(payment.resident.owned_by == 'resident'):
            own_data = FlatAllocation.objects.get(current_resident_id=request.session.get('log_id'))
            owner_data=User.objects.get(id=own_data.owner_id)
        else:
            owner_data = User.objects.get(role="admin")
        payment.paid_to=owner_data
        payment.save()

        # Generate PDF receipt HTML
        receipt_html = render_to_string('resident/receipt_template.html', {
            'payment': payment,
            'resident': resident,
            'flat': flat
        })

        # Ensure static receipts folder exists
        # Path: apartment_app/static/uploads/flats
        app_path = apps.get_app_config('apartment_app').path
        upload_dir = os.path.join(app_path, 'static', 'uploads', 'receipts')
        os.makedirs(upload_dir, exist_ok=True)
        receipt_filename = f"{payment.receipt_no}.pdf"
        full_path = os.path.join(upload_dir, receipt_filename)

        # Save PDF with receipt number
        receipt_path = os.path.join(upload_dir, receipt_filename)

        # Create PDF
        with open(receipt_path, "wb") as f:
            pisa.CreatePDF(receipt_html, dest=f)

        # Save receipt in DB
        receipt = Receipt.objects.create(
            receipt_no=payment.receipt_no,
            file_path=f"uploads/receipts/{receipt_filename}"
        )
        payment.receipt=receipt
        payment.save()
        messages.success(request, "Payment successful! Receipt generated.")
        return redirect('payment')

    if(access == 'flat'):
        return render(request, "resident/make_monthly_payment.html", {"payment": payment, "flat": flat})
    else:
        return render(request, "resident/make_amenity_payment.html", {"payment": payment, "flat": flat})

def complaint_reports(request):
    return render(request, 'admin/Complaint_reports.html')

def profile(request):
    log_id = request.session.get('log_id')
    if not log_id:
        return redirect('login')
    user = User.objects.get(id=log_id)
    role = request.session.get('role')
    if request.method == "POST":
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.email = user.email
        user.phone = request.POST.get("phone")
        user.save()
        messages.success(request, "Profile updated successfully")
        return redirect("profile")
    if role == 'admin':
        return render(request, 'admin/profile.html', {
            'data': user
        })
    elif role == 'resident':
        resident = ResidentProfile.objects.get(user=user)
        return render(request, 'resident/profile.html', {
            'data': user,
            'resident': resident
        })
    elif role == 'security':
        staff = StaffProfile.objects.get(user=user)
        return render(request, 'security/profile.html', {
            'data': user,
            'staff': staff
        })
    else:
        staff = StaffProfile.objects.get(user=user)
        return render(request, 'staff/profile.html', {
            'data': user,
            'staff': staff
        })


def manage_staff(request, staff_id=None):

    # ---------------- DELETE STAFF ----------------
    if request.method == "GET" and request.GET.get("action") == "delete":
        staff = get_object_or_404(StaffProfile, id=staff_id)
        user = staff.user
        staff.delete()
        user.delete()
        messages.success(request, "Staff deleted successfully")
        return redirect("manage_staff")

    # ---------------- ADD / UPDATE STAFF ----------------
    if request.method == "POST":
        staff_id = request.POST.get("staff_id")
        fname = request.POST.get("fname")
        lname = request.POST.get("lname")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        

        role = StaffRole.objects.get(id=request.POST.get("role"))
        if "security" in role.name.lower():
            role_name='security'
        else:
            role_name='staff'
        username = request.POST.get("username")

        # All new staff are Active by default
        status = "active"

        # ---------- UPDATE STAFF ----------
        if staff_id:
            staff = get_object_or_404(StaffProfile, id=staff_id)
            user = staff.user

            user.first_name = fname
            user.last_name = lname
            user.email = email
            user.username = username
            user.status = status
            user.is_active = True
            user.is_staff = True
            phone=phone     # must be True when status is active
            user.save()

            staff.role = role
            staff.save()

            messages.success(request, "Staff updated successfully")

        # ---------- ADD NEW STAFF ----------
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=fname,
                last_name=lname,
                password=username,   # temp password
                status=status,
                role=role_name,
                is_active=True,
                phone=phone,
                is_staff = True
            )

            user.is_active = True   # ensure login allowed
            user.save()

            StaffProfile.objects.create(
                user=user,
                role=role,
                
            )

            messages.success(request, "Staff added successfully")

        return redirect("manage_staff")

    # ---------------- PAGE LOAD ----------------
    staff_list = StaffProfile.objects.select_related("user", "role")
    roles = StaffRole.objects.filter(is_active=True)

    if request.session.get("role") == "admin":
        return render(request, "admin/staffs.html", {
            "staff_list": staff_list,
            "roles": roles
        })
    else:
        return render(request, "security/staffs.html", {
            "staff_list": staff_list,
            "roles": roles
        })

def staff_entry_log(request):
    security = StaffProfile.objects.get(user=request.session.get("log_id"))

    # Staff Entry
    if request.method == "POST" and "mark_entry" in request.POST:
        staff_id = request.POST.get("staff")

        StaffEntryLog.objects.create(staff_id=staff_id)
        return redirect("staff_entry_log")

    # Staff Exit
    if request.method == "POST" and "mark_exit" in request.POST:
        log_id = request.POST.get("log_id")

        log = StaffEntryLog.objects.get(id=log_id)
        log.exit_time = timezone.now()
        log.status = "exited"
        log.save()
        return redirect("staff_entry_log")

    staff_list = StaffProfile.objects.exclude(user__role='security')
    logs = StaffEntryLog.objects.all().order_by("-entry_time")

    return render(request,"security/staff_entry_log.html",{
        "staffs": staff_list,
        "logs": logs
    })

@login_required
def delete_staff(request, staff_id):
    # Security check: only admins should be allowed to delete
    if request.session.get('role') != 'admin':
        messages.error(request, "Access denied.")
        return redirect('dashboard')
        
    # Correctly fetch the staff profile or return a 404 error
    staff = get_object_or_404(StaffProfile, id=staff_id)
    user = staff.user
    
    # Delete both the profile and the user account
    staff.delete()
    user.delete() 
    
    messages.success(request, "Staff member and their user account removed successfully.")
    return redirect('manage_staff')

def approve_resident(request, user_id):
    user = User.objects.get(id=user_id)
    resident=ResidentProfile.objects.get(user_id=user_id)
    user.status = "active"
    user.is_active = 1
    user.save()
    resident.is_approved = 1
    resident.save()
    return redirect("residents")

def manage_staff_roles(request):
    roles = StaffRole.objects.all()

    if request.method == "POST":
        role_name = request.POST.get("role_name")
        role_image = request.FILES.get("role_image")

        if role_name:
            image_path = None

            if role_image:
                app_path = apps.get_app_config('apartment_app').path
                upload_dir = os.path.join(app_path, 'static/uploads/roles')
                os.makedirs(upload_dir, exist_ok=True)

                file_name = role_image.name.replace(" ", "_")
                full_path = os.path.join(upload_dir, file_name)

                with open(full_path, 'wb+') as destination:
                    for chunk in role_image.chunks():
                        destination.write(chunk)

                image_path = f"uploads/roles/{file_name}"

            StaffRole.objects.create(
                name=role_name,
                image=image_path
            )

            return redirect("manage_staff_roles")

    return render(request, 'admin/staff_roles.html', {'roles': roles})

def toggle_staff_role(request, role_id):
    role = StaffRole.objects.get(id=role_id)
    role.is_active = not role.is_active
    role.save()
    return redirect("manage_staff_roles")

def owner_tenant(request):
    user=request.session.get('log_id')
    payments = Payment.objects.filter(paid_to=user)
    return render(request,'resident/my_tenants.html',{'payments':payments})

def residents(request):

    residents = ResidentProfile.objects.select_related(
    'user', 'flat'
    ).filter(
        user__status__in=['active', 'inactive']
    ).order_by('flat__flat_number')

    # Get all active allocations
    allocations = FlatAllocation.objects.select_related(
    "flat",
    "owner",
    "current_resident",
    "current_resident__residentprofile"
    ).filter(is_active=True)

    # Find tenant user ids
    tenant_ids = allocations.values_list("current_resident_id", flat=True)

    owner_allocations = allocations.exclude(owner_id__in=tenant_ids)

    context = {
        "allocation_dict": owner_allocations,
        "all_allocations": allocations
    }

    if request.session.get('role') == 'admin':
        return render(request, 'admin/residents.html', context)
    elif request.session.get('role') == 'staff':
        return render(request, 'staff/residents.html', context)
    else:
        return render(request, 'security/residents.html', context)

def verify_proof(request, resident_id):

    resident = get_object_or_404(ResidentProfile, user_id=resident_id)

    if request.method == "POST":

        verified = request.POST.get("proof_verified")

        if verified == "on":
            resident.proof_verified = 1
        else:
            resident.proof_verified = 0

        resident.save()

        messages.success(request, "Proof verified successfully!")

    return redirect("residents")

def reject_resident(request, pk):
    # 1. Fetch the profile or return 404
    resident = get_object_or_404(ResidentProfile, id=pk)
    
    # 2. Access the linked User object
    user = resident.user
    
    # 3. Update the status attribute
    user.status = "blocked"
    
    # 4. Save the specific user instance
    user.save()
    
    # Optional: You might also want to ensure they aren't 'active' in Django's auth system
    # user.is_active = False
    # user.save()

    return redirect('residents')

def notifications(request):
    return render(request, 'resident/notifications.html')

def notice_list(request):
    role=request.session.get('role')
    if request.method == "POST":
        title = request.POST.get("title")
        message = request.POST.get("message")
        valid_until_str = request.POST.get("valid_until")
        priority = request.POST.get("priority", "normal")
        target_role = request.POST.get("target_role", "all")

        # Convert string → datetime
        valid_until = datetime.strptime(valid_until_str, "%Y-%m-%d")
        valid_until = timezone.make_aware(valid_until)

        Notice.objects.create(
            title=title,
            message=message,
            priority=priority,
            target_role=target_role,
            valid_until=valid_until
        )
    today = date.today()
    if(role=='admin'):
        notices = Notice.objects.all().order_by("-is_pinned", "-created_at")
        return render(request, "admin/notice.html", {"notices": notices,"today":today})
    else:
        notices = Notice.objects.filter(target_role__in=['all', role]).order_by("-is_pinned", "-created_at")
        return render(request, "resident/notice.html", {"notices": notices,"today":today})

def toggle_amenity_status(request, amenity_id):
    amenity = get_object_or_404(Amenity, id=amenity_id)

    if amenity.status == "Active":
        amenity.status = "Inactive"
        amenity.is_bookable = False   # Also stop booking
    else:
        amenity.status = "Active"
        amenity.is_bookable = True

    amenity.save()
    return redirect("amenities")   # use your amenity page name

from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Complaint, ResidentProfile, Notification, User


def complaints(request):
    role = request.session.get('role')
    log_id = request.session.get('log_id')

    if not log_id:
        messages.error(request, "Please login first")
        return redirect("home")

    user = User.objects.get(id=log_id)

    # ================= RESIDENT SUBMIT COMPLAINT =================
    if role == "resident" and request.method == "POST":
        issue = request.POST.get('issue')
        c_type = request.POST.get('complaint_type')
        if request.POST.get('urg'):
            urgent=1
        else:
            urgent=0
        Complaint.objects.create(
            resident=user,
            issue=issue,
            complaint_type=c_type,
            status='pending',
            urgent=urgent
        )

        # Notify Admin
        admin_user = User.objects.filter(role="admin").first()
        if admin_user:
            Notification.objects.create(
                user=admin_user,
                title="New Complaint",
                message=f"{user.first_name} submitted a complaint."
            )

        return redirect('complaints')

    # ================= ADMIN REPLY =================
    if role == "admin" and request.method == "POST":
        complaint_id = request.POST.get('complaint_id')
        reply = request.POST.get('admin_response')

        complaint = Complaint.objects.get(id=complaint_id)
        complaint.admin_response = reply
        complaint.status = "replied"
        complaint.save()

        # Notify Resident
        Notification.objects.create(
            user=complaint.resident,
            title="Complaint Replied",
            message="Admin replied to your complaint."
        )

        return redirect('complaints')

    # ================= FETCH DATA =================
    if role == "admin":
        all_complaints = Complaint.objects.select_related(
            'resident'
        ).order_by('-created_at')

        # Filters
        filter_type = request.GET.get('type')
        if filter_type == "urgent":
            all_complaints = all_complaints.filter(urgent=True)
        elif filter_type == "general":
            all_complaints = all_complaints.filter(urgent=False)

        filter_reply = request.GET.get('reply')
        if filter_reply == "replied":
            all_complaints = all_complaints.exclude(admin_response__exact='')
        elif filter_reply == "notreplied":
            all_complaints = all_complaints.filter(
                Q(admin_response__exact='') | Q(admin_response__isnull=True)
            )

        # Attach flat number (Clean way)
        resident_profiles = ResidentProfile.objects.select_related('flat')

        profile_dict = {
            rp.user_id: rp.flat.flat_number if rp.flat else "undefined"
            for rp in resident_profiles
        }

        for c in all_complaints:
            c.flat_number = profile_dict.get(c.resident_id, "undefined")

        template_name = "admin/complaints.html"

    elif role == "resident":
        all_complaints = Complaint.objects.filter(
            resident=user
        ).order_by('-created_at')

        template_name = "resident/complaints.html"

    else:
        messages.error(request, "Unauthorized access")
        return redirect("home")

    return render(request, template_name, {
        "complaints": all_complaints,
        "role": role
    })

def flat_gallery(request, flat_id):
    flat = Flat.objects.get(id=flat_id)
    images = flat.images.all()
    return render(request, "admin/flat_gallery.html", {"flat": flat, "images": images})



def flats_and_payments(request):
    role = request.session.get("role")
    user = User.objects.get(id=request.session.get("log_id"))

    # ================= ADMIN =================
    if role == "admin":

        # ✅ Add image count annotation
        flats_list = Flat.objects.annotate(
            image_count=Count("images")
        ).order_by("flat_number")

        # -------- FILTERS ----------
        status_filter = request.GET.get("status")
        bhk_filter = request.GET.get("bhk")
        availability_filter = request.GET.get("availability")

        if status_filter:
            flats_list = flats_list.filter(status=status_filter)

        if bhk_filter:
            flats_list = flats_list.filter(bhk_type=bhk_filter)

        if availability_filter == "available":
            flats_list = flats_list.filter(is_available=True)

        elif availability_filter == "occupied":
            flats_list = flats_list.filter(is_available=False)


        paginator = Paginator(flats_list, 8)
        page_number = request.GET.get("page")
        flats = paginator.get_page(page_number)

        residents = ResidentProfile.objects.filter(
            is_approved=True,
            flat__isnull=False
        )

        if request.method == "POST":

            # --------- GENERATE MONTHLY BILLS ----------
            if "generate_bills" in request.POST:

                for r in residents:
                    flat = r.flat
                    amount = (flat.monthly_rent or 0) + (flat.maintenance_charge or 0)
                    if(r.user.owner_status == '1'):
                        OwnerPayment.objects.create(
                        user=user,
                        flat=r.flat,
                        total_amount=amount
                    )
                    else:
                        Payment.objects.get_or_create(
                            resident=r,
                            status="pending",
                            description="Monthly Rent & Maintenance",
                            amount=amount
                        )

                messages.success(request, "Monthly bills generated")
                return redirect("flats_and_payments")

            # --------- ADD / UPDATE FLAT ----------
            if "save_flat" in request.POST:

                flat_id = request.POST.get("flat_id")
                flat = Flat.objects.get(id=flat_id) if flat_id else Flat()

                flat.flat_number = request.POST["flat_number"]
                flat.description = request.POST["description"]
                flat.bhk_type = request.POST["bhk_type"]
                flat.bedrooms = request.POST["bedrooms"]
                flat.bathrooms = request.POST["bathrooms"]
                flat.block = request.POST["block"]
                flat.floor_number = request.POST["floor_number"]
                flat.built_up_area = request.POST["built_up_area"]
                flat.status = request.POST.get("status")
                flat.furnished = request.POST.get("furnished")
                flat.monthly_rent = float(request.POST.get("monthly_rent") or 0)
                if flat.status == "sale":
                    flat.purchase_price = float(request.POST["purchase_rate"])
                else:
                    flat.purchase_price = 0

                flat.is_available = True


                flat.maintenance_charge = request.POST.get("maintenance_charge") or 0
                flat.status = request.POST["status"]
                flat.is_available = True

                flat.maintenance_charge = request.POST.get("maintenance_charge") or 0
                flat.status = request.POST["status"]
                flat.is_available = True

                # -------- Save Cover Image ----------
                if request.FILES.get("flat_image"):
                    file = request.FILES["flat_image"]

                    app_path = apps.get_app_config('apartment_app').path
                    upload_dir = os.path.join(app_path, 'static', 'uploads', 'flats')
                    os.makedirs(upload_dir, exist_ok=True)

                    file_name = file.name.replace(" ", "_")
                    full_path = os.path.join(upload_dir, file_name)

                    with open(full_path, "wb+") as destination:
                        for chunk in file.chunks():
                            destination.write(chunk)

                    flat.flat_image = f"uploads/flats/{file_name}"

                flat.save()

                messages.success(request, "Flat saved successfully")
                return redirect("flats_and_payments")

        return render(request, "admin/flats.html", {
            "flats": flats
        })

    # ================= RESIDENT =================
    else:
        resident = ResidentProfile.objects.get(user=user)
        flat = resident.flat
        payments = Payment.objects.filter(resident=resident).order_by("-payment_date")

        return render(request, "resident/payment.html", {
            "flat": flat,
            "payments": payments
        })

def community_chat(request):
    if request.method == "POST":
        user=User.objects.get(id=request.session.get('log_id'))
        msg_text = request.POST.get('message')
        parent_id = request.POST.get('parent_id') # Get parent ID from hidden input
        
        parent_msg = None
        if parent_id:
            parent_msg = CommunityChat.objects.get(id=parent_id)

        if msg_text:
            CommunityChat.objects.create(
                resident=user,
                message=msg_text,
                parent=parent_msg
            )
        return redirect('community_chat')

    # Fetch only top-level messages (those without a parent)
    # We will show replies nested inside them in the template
    messages = CommunityChat.objects.filter(parent=None).order_by('-created_at')[:50]
    return render(request, 'resident/community.html', {
    'messages': reversed(messages),
    'current_user_id': request.session.get('log_id')
})

def staff_worklog(request):
    data=request.session.get('log_id')
    staff = StaffProfile.objects.get(user=data)
    req=SupportRequest.objects.filter(task__assigned_staff__user=data).order_by('-created_at')
    logs = StaffWorkLog.objects.filter(
        assigned_staff=staff,work_status='completed'
    ).order_by('-created_at')

    return render(request, "staff/worklog.html", {
        "logs": logs,
        "requests": req
    })


def requests(request):

    user=User.objects.get(id=request.session.get('log_id'))
    if request.method == "POST":
        if request.POST.get('urg'):
            urgent=1
        else:
            urgent=0
        SupportRequest.objects.create(
            resident=user,
            title=request.POST['title'],
            description=request.POST['description'],
            urgent=urgent
        )
        return redirect('requests')

    requests = SupportRequest.objects.filter(resident=user).order_by('-created_at')
    return render(request,'resident/support.html',{'requests':requests})

def maintanance_confirmation(request,id):
    if request.method == "POST":
        log=StaffWorkLog.objects.get(id=id)
        log.resident_confirmation = 1
        log.save()
    return redirect('requests')

def staff_tasks(request):
    data=User.objects.get(id=request.session.get('log_id'))
    staff = StaffProfile.objects.get(user=data)
    resident=ResidentProfile.objects.all()
    tasks=SupportRequest.objects.filter(task__assigned_staff__user__id=request.session.get('log_id'),status='assigned',task__work_status__in=['not_started','in_progress','reassigned'])
    
    if request.method == "POST":
        task_id = request.POST.get('task_id')
        selected_task=SupportRequest.objects.get(task_id=task_id)
        log = StaffWorkLog.objects.get(id=task_id, assigned_staff=staff)

        # If not started → start
        if log.work_status == 'not_started':
            log.work_status = 'in_progress'
            log.started_time = timezone.now()
            log.save()

        # If in progress → complete
        elif log.work_status == 'in_progress':
            log.work_status = 'completed'
            log.ending_time = timezone.now()
            selected_task.status='solved'
            selected_task.save()
            log.save()

        return redirect('staff_tasks')

    return render(request, 'staff/tasks.html', {'tasks': tasks ,'resident':resident})

def admin_requests(request):

    # Base queryset
    requests_qs = SupportRequest.objects.select_related(
        'resident__residentprofile__flat', 'task'
    ).order_by('-created_at')

    staffs = StaffProfile.objects.all()

    # --- FILTERS ---
    filter_type = request.GET.get('type')
    if filter_type == "urgent":
        requests_qs = requests_qs.filter(urgent=True)
    elif filter_type == "general":
        requests_qs = requests_qs.filter(urgent=False)

    filter_status = request.GET.get('status')
    if filter_status == "pending":
        requests_qs = requests_qs.filter(task__isnull=True)
    elif filter_status == "assigned":
        requests_qs = requests_qs.filter(task__isnull=False).exclude(task__work_status='completed')
    elif filter_status == "completed":
        requests_qs = requests_qs.filter(task__work_status='completed')

    # --- HANDLE POST ---
    if request.method == "POST":

        # ------------------------
        # ASSIGN STAFF
        # ------------------------
        if 'assign' in request.POST:
            assignee = StaffProfile.objects.get(id=request.POST['role_id'])
            req = SupportRequest.objects.get(id=request.POST['req_id'])

            # Create staff work log FIRST
            worklog = StaffWorkLog.objects.create(
                assigned_staff=assignee,
                work_status='not_started',
                date=timezone.now().date()
            )

            # Update support request with task_id
            req.assigned_role = assignee
            req.status = "assigned"
            req.task = worklog   # 🔥 linking task
            req.save()

            return redirect('admin_requests')

        # ------------------------
        # MARK COMPLETED
        # ------------------------
        if 'complete' in request.POST:
            req = SupportRequest.objects.get(id=request.POST['req_id'])

            req.status = "completed"
            req.save()

            if req.task:
                req.task.work_status = 'completed'
                req.task.ending_time = timezone.now()
                if not req.task.started_time:
                    req.task.started_time = timezone.now()
                req.task.save()

            return redirect('admin_requests')

    return render(request, 'admin/requests.html', {
        'requests': requests_qs,
        'roles': staffs
    })

def amenities(request):   
    days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
    role=request.session.get('role')
    blocked_dates = AmenityOffDay.objects.all()
    off_days_map = {}

    for a_id, day in AmenityOffDay.objects.values_list('amenity_id', 'day'):
        off_days_map.setdefault(a_id, []).append(day)

    # Convert to list of day strings
    off_days = list(blocked_dates.values_list('amenity_id', 'day'))
    amenities = Amenity.objects.all()
    slots=AmenityTimeSlot.objects.all()
    if request.method == "POST":
        name = request.POST.get('name')
        description = request.POST.get('description')
        charge = request.POST.get('charge')
        max_people = request.POST.get('max_people')
        is_bookable = request.POST.get('is_bookable')
        booking_duration = request.POST.get('booking_duration')
        icon = request.FILES.get('icon')   # ✅ correct

        image_path = None

        if icon:
            app_path = apps.get_app_config('apartment_app').path
            upload_dir = os.path.join(app_path, 'static', 'uploads', 'amenities')
            os.makedirs(upload_dir, exist_ok=True)

            file_name = icon.name.replace(" ", "_")
            full_path = os.path.join(upload_dir, file_name)

            with open(full_path, 'wb+') as destination:
                for chunk in icon.chunks():   # ✅ correct
                    destination.write(chunk)

            image_path = f"uploads/amenities/{file_name}"

        Amenity.objects.create(
            name=name,
            description=description,
            charge=charge,
            image=image_path,    # match your model field
            max_people=max_people,
            is_bookable=True if is_bookable == 'on' else False,
            booking_duration=booking_duration 
        )

        messages.success(request, "Amenity added successfully")
        return redirect('amenities')
    if role=='admin':
        return render(request, 'admin/amenities.html', {'amenities': amenities,'slots':slots,'off_days_map': off_days_map,
    'days': days})
    else:
        booking = AmenityBooking.objects.filter(resident_id=request.session.get('log_id'))
        amenities = Amenity.objects.filter(is_bookable = 1)
        booking_info=[]
        if booking.count()>1:
            for i in booking:
                booking_info.append(i.amenity_id)
        return render(request, 'resident/amenities.html', {'booking': booking, 'days': days, 'slots': slots, 'off_days_map': off_days_map, 'amenities': amenities, 'slots': slots, 'blocked_dates': blocked_dates, 'booking_info': booking_info})

def amenity_slots(request):
    if request.method == "POST":
        amenity_id = request.POST.get("amenity_hidden")

        start_time = request.POST.get("start_time")
        end_time = request.POST.get("end_time")
        blocked_dates = AmenityOffDay.objects.all()
        AmenityTimeSlot.objects.create(
            amenity_id=amenity_id,
            start_time=start_time,
            end_time=end_time,
        )
        messages.success(request, "Time slot added")

    return redirect('amenities')

def amenity_block_dates(request):
    if request.method == "POST":
        amenity_id = request.POST.get('amenity_hidden')
        day = request.POST.get('day')

        AmenityOffDay.objects.create(
            amenity_id=amenity_id,
            day=day
        )
        messages.success(request, "successfully Updated")
    return redirect('amenities')

    
def expire_old_bookings():
    today = timezone.now().date()

    # 1 Day expiry
    one_day_expired = AmenityBooking.objects.filter(
        amenity__booking_duration='1d',
        booking_status__in=['Pending', 'Approved'],
        booking_date__lte=today - timedelta(days=1)
    )

    # 1 Month expiry
    one_month_expired = AmenityBooking.objects.filter(
        amenity__booking_duration='1m',
        booking_status__in=['Pending', 'Approved'],
        booking_date__lte=today - relativedelta(months=1)
    )

    one_day_expired.update(booking_status='Expired')
    one_month_expired.update(booking_status='Expired')

def amenity_bookings(request):
    role = request.session.get('role')
    # ---------------- ADMIN ----------------
    if role == "admin":
        bookings = AmenityBooking.objects.select_related(
            "amenity", "resident", "time_slot"
        ).order_by("-id")

        if request.method == "POST":
            booking_id = request.POST.get("booking_id")
            action = request.POST.get("action")

            booking = get_object_or_404(AmenityBooking, id=booking_id)

            if action == "approve":
                booking.booking_status = "Approved"
            elif action == "reject":
                booking.booking_status = "Rejected"

            booking.save()
            messages.success(request, "Booking status updated successfully")

            return redirect("amenity_bookings")

        return render(request, "admin/amenity_bookings.html", {
            "bookings": bookings
        })

    # ---------------- RESIDENT ----------------
    else:
        amenities = Amenity.objects.filter(is_bookable=1)
        user=User.objects.get(id=request.session['log_id'])
        my_bookings = AmenityBooking.objects.filter(
            resident=user
        ).select_related("amenity", "time_slot").order_by("-booking_date")

        # So we can mark booked amenities in UI
        booked_amenity_ids = my_bookings.values_list("amenity_id", flat=True)
        if request.method == "POST":
            amenity_id = request.POST.get("amenity_id")
            date = request.POST.get("booking_date")
            slot_id = request.POST.get("time_slot")

            amenity = Amenity.objects.get(id=amenity_id)
            slot = AmenityTimeSlot.objects.get(id=slot_id)

            # Prevent duplicate booking
            if AmenityBooking.objects.filter(
                amenity=amenity,
                booking_date=date,
                time_slot=slot,
                booking_status__in=["Pending","Approved"]
            ).exists():
                messages.error(request,"This slot is already booked!")
                return redirect("amenities")

            AmenityBooking.objects.create(
                amenity=amenity,
                resident=user,
                booking_date=date,
                time_slot=slot,
                amount=amenity.charge,
                payment_status="Unpaid",
                booking_status="Pending"
            )

        return redirect("amenity_payments")    

def amenity_payments(request):
    role = request.session.get('role')
    user_id = request.session.get('log_id')
    
    # ADMIN VIEW → all payments
    if role == 'admin':
        payments = AmenityPayment.objects.select_related(
            "booking", "booking__amenity", "booking__resident"
        )

        total_income = sum(p.booking.amenity.charge for p in payments)

        return render(request, 'admin/amenity_payments.html', {
            'payments': payments,
            'total_income': total_income
        })

    # RESIDENT VIEW → only their payments
    else:
        if request.method == 'POST':
            booking= AmenityBooking.objects.get(id=request.POST['booking']) 
            resident=ResidentProfile.objects.get(user_id=booking.resident_id)
            return render(request, 'resident/make_amenity_payment.html', {
                'booking': booking,
                'resident':resident,
            })
        else:
            pending= AmenityBooking.objects.filter(
                resident=user_id
            )
            payments = AmenityPayment.objects.filter(
                booking__resident_id=user_id
            ).select_related("booking", "booking__amenity")

            total_income = sum(p.booking.amenity.charge for p in payments)

            return render(request, 'resident/amenity_payments.html', {
                'payments': payments,
                'total_income': total_income,
                'pending_bookings': pending
            })

def amenity_payment_success(request, booking_id):
    booking = AmenityBooking.objects.get(id=booking_id)

    # mark booking as paid
    booking.payment_status = "Paid"
    booking.booking_status = "Approved"
    booking.save()

    # save payment record
    AmenityPayment.objects.create(
        booking=booking,
        resident=booking.resident,
        payment_date=timezone.now()
    )
    Notification.objects.create(
        user=booking.resident,
        title=f"Amenity Payment {booking.amenity.charge}/- Successful",
        message=f"{booking.amenity.name} booking confirmed."
    )


    messages.success(request, "Payment successful. Booking confirmed.")
    return redirect("amenity_payments")

def export_amenity_payments_csv(request):
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="amenity_payments.csv"'

    writer = csv.writer(response)
    # Write header row
    writer.writerow(['User', 'Amenity', 'Booking Date', 'Amount', 'Payment Mode', 'Status'])

    # Fetch all payment records
    payments = AmenityPayment.objects.select_related('booking', 'resident')

    for p in payments:
        writer.writerow([
            p.resident.get_full_name(),  # or p.user.username
            p.booking.amenity.name,
            p.booking.booking_date.strftime("%d %b %Y"),
            p.booking.amenity.charge,
            p.payment_mode,
            p.status
        ])

    return response


def amenity_analytics(request):

    # ---------------- Summary Cards ----------------

    total_bookings = AmenityBooking.objects.count()

    # Amenity Revenue = Sum of amenity charge from successful amenity payments
    amenity_revenue = AmenityPayment.objects.filter(
        status='Success'
    ).aggregate(
        total=Sum(F('booking__amenity__charge'))
    )['total'] or 0

    # Apartment revenue (normal apartment payments)
    apartment_revenue = Payment.objects.filter(
        status='paid'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    total_revenue = float(amenity_revenue) + float(apartment_revenue)

    total_residents = User.objects.filter(role='resident',status='active').count()

    # ---------------- Most Booked Amenity ----------------

    popular_amenity = AmenityBooking.objects.values(
        'amenity__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count').first()

    if popular_amenity:
        popular_amenity_name = popular_amenity['amenity__name']
        popular_amenity_count = popular_amenity['count']
    else:
        popular_amenity_name = "N/A"
        popular_amenity_count = 0

    # ---------------- Monthly Revenue ----------------

    current_year = timezone.now().year
    revenue_per_month = []
    months = []

    for month in range(1, 13):

        amenity_monthly = AmenityPayment.objects.filter(
            status='Success',
            payment_date__year=current_year,
            payment_date__month=month
        ).aggregate(
            total=Sum(F('booking__amenity__charge'))
        )['total'] or 0

        apartment_monthly = Payment.objects.filter(
            status='paid',
            payment_date__year=current_year,
            payment_date__month=month
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        revenue_per_month.append(float(amenity_monthly) + float(apartment_monthly))
        months.append(calendar.month_abbr[month])

    # ---------------- Amenity Popularity ----------------

    amenity_stats = AmenityBooking.objects.values(
        'amenity__name'
    ).annotate(
        bookings_count=Count('id')
    ).order_by('-bookings_count')

    amenity_labels = [a['amenity__name'] for a in amenity_stats]
    amenity_bookings = [a['bookings_count'] for a in amenity_stats]

    context = {
        'total_bookings': total_bookings,
        'total_revenue': total_revenue,
        'total_residents': total_residents,
        'popular_amenity_name': popular_amenity_name,
        'popular_amenity_count': popular_amenity_count,
        'months': months,
        'revenue_per_month': revenue_per_month,
        'amenity_labels': amenity_labels,
        'amenity_bookings': amenity_bookings,
    }

    return render(request, 'admin/analytics.html', context)

def export_amenity_bookings_csv(request):
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="amenity_bookings.csv"'

    writer = csv.writer(response)
    # Write header row
    writer.writerow(['User', 'Amenity', 'Booking Date', 'Time Slot', 'Number of People', 'Status', 'Amount Paid'])

    # Fetch all bookings
    bookings = AmenityBooking.objects.all().select_related('amenity', 'resident', 'time_slot')

    for b in bookings:
        writer.writerow([
            b.resident.get_full_name(),  # or b.user.username
            b.amenity.name,
            b.booking_date.strftime("%d %b %Y"),
            f"{b.time_slot.start_time.strftime('%H:%M')} – {b.time_slot.end_time.strftime('%H:%M')}",
            b.amenity.max_people,
            b.amenity.status,
            b.amount
        ])

    return response

def rent_flat_to_new_resident(request):
    owner = User.objects.get(id=request.session['log_id'])
    
    if request.method == "POST":

        flat = Flat.objects.get(id=request.POST['flat'])
        # -------- FILE UPLOAD --------
        aadhaar_file = request.FILES.get('aadhaar')
        photo_file = request.FILES.get('photo')

        aadhaar_path = None
        photo_path = None

        upload_dir = os.path.join(settings.BASE_DIR, 'apartment_app', 'static', 'uploads', 'proofs')
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = str(int(time.time()))

        # Save Aadhaar
        # -------- SAVE AADHAAR --------
        if aadhaar_file:
            ext = os.path.splitext(aadhaar_file.name)[1]
            aadhaar_name = f"{uuid.uuid4().hex}{ext}"

            aadhaar_full_path = os.path.join(upload_dir, aadhaar_name)

            with open(aadhaar_full_path, 'wb+') as f:
                for chunk in aadhaar_file.chunks():
                    f.write(chunk)

            aadhaar_path = f"uploads/proofs/{aadhaar_name}"

        # Save Photo
        if photo_file:
            ext = os.path.splitext(photo_file.name)[1]
            photo_name = f"{uuid.uuid4().hex}{ext}"

            photo_full_path = os.path.join(upload_dir, photo_name)

            with open(photo_full_path, 'wb+') as f:
                for chunk in photo_file.chunks():
                    f.write(chunk)

            photo_path = f"uploads/proofs/{photo_name}"

        # Step 1 - Create User
        user = User.objects.create(
            username=request.POST['username'],
            first_name=request.POST['fname'],
            last_name=request.POST['lname'],
            phone=request.POST['phone'],
            email=request.POST['email'],
            role="resident",
            status="active",
            password=make_password(request.POST['password'])
        )

        ResidentProfile.objects.create(
            user=user,
            flat=flat,
            is_approved=True,
            owned_by = 'resident',
            aadhaar=aadhaar_path,
            photo=photo_path
        )

        # Step 2 - Close owner's allocation
        FlatAllocation.objects.filter(
            flat=flat,
            owner=owner,
            is_active=True
        ).update(
            is_active=False,
            end_date=timezone.now()
        )

        # Step 3 - Create new allocation
        flat = FlatAllocation.objects.create(
            flat=flat,
            owner=owner,
            current_resident=user,
            allocation_type=request.POST['allocation_type'],
            start_date=request.POST['start_date'],
            end_date=request.POST.get('end_date') or None,
            is_active=True
        )
        Payment.objects.create(
            resident=user.residentprofile,
            amount=flat.flat.monthly_rent + flat.flat.maintenance_charge,
            status="pending",
            paid_to=owner
        )

        return redirect("dashboard")


def add_visitor(request):
    staff = StaffProfile.objects.get(user=request.session.get("log_id"))
    residents=ResidentProfile.objects.all()

    if request.method == "POST":
        name = request.POST.get("visitor_name")
        flat_no = request.POST.get("flat_no")
        purpose = request.POST.get("purpose")

        flat = Flat.objects.get(flat_number=flat_no)
        resident = ResidentProfile.objects.filter(
            flat_id=flat.id,
            is_approved='1',
            user__status='active'
            ).last()
        # if resident.count == 1:
        #     resident = ResidentProfile.objects.get(
        #     flat_id=flat.id,
        #     is_approved='1'),
        #     owned_by='admin'
        # else:            
        #     resident = ResidentProfile.objects.get(
        #     flat_id=flat.id,
        #     is_approved='1',
        #     owned_by='resident'
        #     )
        image = request.FILES.get('image')

        visitor = Visitor.objects.create(
            visitor_name=name,
            resident=resident,
            registered_by=staff,
            purpose=purpose,
            approval_status="pending"
        )

        if image:
            app_path = apps.get_app_config('apartment_app').path
            upload_dir = os.path.join(app_path, 'static', 'uploads', 'visitors')
            os.makedirs(upload_dir, exist_ok=True)

            file_name = image.name.replace(" ", "_")
            full_path = os.path.join(upload_dir, file_name)

            with open(full_path, 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)

                # Save relative static path in DB
                visitor.image = f"uploads/visitors/{file_name}"
                visitor.save()
            Notification.objects.create(
                user=User.objects.get(id=resident.user_id),
                title="New Visitor Arrived",
                message=f"New Visitor arrived"
            )


        return redirect("add_visitor")

    visitors = Visitor.objects.filter(registered_by=staff).order_by("-id")
    flats = Flat.objects.filter(is_available = 0)

    return render(request,"security/add_visitor.html",{
        "visitors": visitors,
        "flats": flats,
        "residents":residents
    })

def visitor_gate(request):
    user_id = request.session.get("log_id")
    role = request.session.get("role")

    # Resident approve / reject
    if request.method == "POST" and "resident_action" in request.POST:
        visitor = Visitor.objects.get(
            id=request.POST.get("visitor_id"),
        )
        visitor.approval_status = request.POST.get("action")
        visitor.save()
        return redirect("visitor_gate")

    # Security allow entry
    if request.method == "POST" and "allow_entry" in request.POST:
        visitor = Visitor.objects.get(id=request.POST.get("visitor_id"))

        if visitor.approval_status == "approved":
            visitor.approval_status = "entered"
            visitor.entry_time = timezone.now()
            visitor.save()
        return redirect("visitor_gate")

    # Security mark exit
    if request.method == "POST" and "mark_exit" in request.POST:
        visitor = Visitor.objects.get(id=request.POST.get("visitor_id"))
        visitor.approval_status = "exited"
        visitor.exit_time = timezone.now()
        visitor.save()
        return redirect("visitor_gate")
    # Data for screens
    if role == "security":
        visitors = Visitor.objects.all().order_by("-id")
        return render(request,"security/add_visitor.html",{"visitors":visitors})

    elif role == "resident":
        resident_profile=ResidentProfile.objects.get(user=user_id)
        visitors = Visitor.objects.filter(resident=resident_profile.id)
        return render(request,"resident/visitor_requests.html",{"visitors":visitors})

    else:
        visitors = Visitor.objects.all()
        return render(request,"admin/visitors.html",{"visitors":visitors})

def parcel_management(request):
    role = request.session.get("role")
    user_id = request.session.get("log_id")

    # ================= SECURITY =================
    if role == "security":
        staff = StaffProfile.objects.get(user_id=user_id)

        # ➕ Add parcel
        if request.method == "POST" and "add_parcel" in request.POST:
            resident_id = request.POST.get("resident")
            courier = request.POST.get("courier")

            Parcel.objects.create(
                resident_id=resident_id,
                courier_name=courier,
            )
            userid=ResidentProfile.objects.get(id=resident_id)
            Notification.objects.create(
                user=User.objects.get(id=userid.user_id),
                title="New Parcel Arrived",
                message=f"Parcel from {courier}"
            )

            return redirect("parcel_management")

        # ✅ Mark collected
        if request.method == "POST" and "collect_parcel" in request.POST:
            parcel_id = request.POST.get("parcel_id")
            parcel = Parcel.objects.get(id=parcel_id)
            parcel.status = "collected"
            parcel.save()
            return redirect("parcel_management")

        parcels = Parcel.objects.all().order_by("-received_time")
        residents = ResidentProfile.objects.filter(is_approved=1, user__is_active=1)

        return render(request,"security/parcel_management.html",{
            "parcels": parcels,
            "residents": residents
        })


    # ================= ADMIN =================
    if role == "admin":
        parcels = Parcel.objects.all().order_by("-received_time")

        return render(request,"admin/parcel_details.html",{
            "parcels": parcels
        })


    # ================= RESIDENT =================
    else:
        resident = ResidentProfile.objects.get(user_id=user_id)
        parcels = Parcel.objects.filter(resident=resident).order_by("-received_time")

        return render(request,"resident/parcels.html",{
            "parcels": parcels
        })
def admin_vacate_requests(request):
    

    vacate_requests = VacateRequest.objects.select_related(
        "resident", "flat"
    ).filter(
        allocation__owner_id=request.session.get("log_id")
    ).order_by("-request_date")

    # Check pending payments
    # resident=ResidentProfile.objects.get()
    for req in vacate_requests:
        req.has_pending = Payment.objects.filter(
            resident_id=req.resident_id,
            status="pending"
        ).exists()

    return render(
        request,
        "admin/vacate_requests.html",
        {"requests": vacate_requests}
    )
def owner_vacate_requests(request):

    requests = VacateRequest.objects.select_related(
        "resident", "flat"
    ).filter(allocation__owner_id=request.session.get("log_id")).order_by("-request_date")
    for req in requests:
        user=ResidentProfile.objects.get(user_id = req.resident_id)
        req.has_pending = Payment.objects.filter(
            resident=user.id,
            status="pending"
        ).exists()
    return render(
        request,
        "resident/vacate_requests.html",
        {"requests": requests}
    )

def request_vacate(request):
    user_id = request.session.get("log_id")
    user = User.objects.get(id=user_id)
    allocation = FlatAllocation.objects.get(
        current_resident_id=user_id,
        is_active=True
    )
    flat = allocation.flat
    penalty = int(flat.monthly_rent) / 2
    if(VacateRequest.objects.filter(resident=user).count() == 0):
        payment=Payment.objects.create(
            resident=user.residentprofile,
            amount=penalty,
            status="pending",
        )

        vacate = VacateRequest.objects.create(
            resident=user,
            flat=flat,
            allocation=allocation,
            penalty_amount=penalty,
            payment=payment
        )
        messages.success(
            request,
            "Vacate request submitted. Pay penalty to continue."
        )
    return redirect("payment")

def approve_vacate(request, id):

    vacate = VacateRequest.objects.get(id=id)

    allocation = vacate.allocation
    flat = vacate.flat

    # deactivate allocation
    allocation.is_active = False
    allocation.end_date = date.today()
    allocation.save()

    # make flat available
    if(request.session.get('role')=='admin'):
        flat.is_available = True
        flat.save()

    user=User.objects.get(id=vacate.resident.id)
    user.status='vacated'
    user.is_active=0
    user.save()

    vacate.status = "approved"
    vacate.save()

    messages.success(request, "Resident vacated successfully.")

    if(request.session.get('role')=='admin'):
        return redirect("admin_vacate_requests")
    else:
        return redirect("owner_vacate_requests")

def reject_vacate(request, id):
    # Admin check
    if request.session.get("role") != "admin":
        return redirect("login")
    vacate_request = get_object_or_404(VacateRequest, id=id)

    # Update status
    vacate_request.status = "rejected"
    vacate_request.save()

    messages.warning(request, "Vacate request rejected.")

    return redirect("admin_vacate_requests")

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            user = User.objects.get(email=email)
            return redirect("verify_user", user_id=user.id)
        except User.DoesNotExist:
            messages.error(request, "Email not registered")

    return render(request, "home/forgot_password.html")


# Step 2: Confirm user identity (simple academic verification)
def verify_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        username = request.POST.get("username")

        if username == user.username:
            return redirect("edit_password", user_id=user.id)
        else:
            messages.error(request, "Username does not match")

    return render(request, "home/verify_user.html", {"user": user})


# Step 3: Set new password
def edit_password(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 == password2:
            user.set_password(password1)
            user.save()
            messages.success(request, "Password updated successfully")
            return redirect("login")
        else:
            messages.error(request, "Passwords do not match")

    return render(request, "home/reset_password.html")

def logout_view(request):
    logout(request)
    return redirect('login')
