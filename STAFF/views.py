from django.shortcuts import render,redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
from MAIN_APP.models import *
from django.shortcuts import get_object_or_404
from django.db.models import Q
 
# Create your views here.
@user_passes_test(lambda u:u.is_authenticated and u.is_superuser,login_url='login_page' )
def staff(request):
    users = User.objects.exclude(is_superuser=True).order_by('-id')
    if request.method == "GET":
        search=request.GET.get("search")
        date=request.GET.get("date")
        users = User.objects.exclude(is_superuser=True).order_by('-id')
        if search:
            keyword = search.lower()
            if keyword == "staff":
                users = User.objects.filter(is_staff=True).exclude(is_superuser=True)
            else:
                users = User.objects.filter(
                    Q(first_name__icontains=search) |
                    Q(id__icontains=search) |
                    Q(email__icontains=search)
                ).exclude(is_superuser=True)
        elif date:
            users = User.objects.filter(Q(date_joined__date=date) | Q(last_login__date=date))
        else:
            users = User.objects.exclude(is_superuser=True).order_by('-id')
    
    return render(request,"staff.html",locals())

@login_required
def activate_staff(request,id):
    user = User.objects.get(id=id)
    if user.is_staff:
        user.is_staff = False
        user.save()
        return redirect('staff')
    else:
        user.is_staff = True
        user.save()
    return redirect('staff')


@login_required
def add_staff(request):
    if request.method == "POST":
        f_name = request.POST.get("f_name")
        l_name = request.POST.get("l_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        address = request.POST.get("address")
        phone = request.POST.get("phone")
        profile_pic=request.FILES.get("profile_pic")

        user=User.objects.create(
            username=f_name,
            first_name = f_name,
            last_name = l_name,
            email = email,
            is_staff = 1
        )

        user.set_password(password)
        user.save()

        user_profile = UserProfile.objects.create(
            user = user,
            address = address,
            phone = phone,
        )

        if profile_pic:
            user_profile.profile_pic = profile_pic

        user_profile.save()

        messages.success(request,"Staff added successfully!")
        return redirect(staff)

    return render(request,"add_staff.html")


@login_required
def update_staff(request,id):
    user=User.objects.get(id=id)
    user_profile = UserProfile.objects.get(user=user)
    
    if request.method == "POST":
        user.first_name = request.POST.get("f_name")
        user.last_name = request.POST.get("l_name")
        user.email = request.POST.get("email")
        new_password = request.POST.get("password")
        user_profile.address = request.POST.get("address")
        user_profile.phone = request.POST.get("phone")
        new_profile_pic=request.FILES.get("profile_pic")
        

        if new_password:
            user.set_password(new_password)
        if new_profile_pic:
            user_profile.profile_pic=new_profile_pic

        user.save()
        user_profile.save()
        messages.success(request,"Staff Updated Successfully")
        return redirect(staff)
    return render(request,"update_staff.html",locals())


@login_required
def delete_staff(request,id):
    user=User.objects.get(id=id)
    print(user)
    user.delete()
    return redirect(staff)

@login_required
def view_staff(request,id):
    user=User.objects.get(id=id)
    user_profile=get_object_or_404(UserProfile,user=user)
    return render(request,"view_staff.html",locals())