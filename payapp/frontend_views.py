from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from datetime import date

from models import UserPayment

# /login
def login_view(request):
    if request.method == 'POST':
        username  = request.POST['username']
        password  = request.POST['password']
        user      = authenticate(username=username, password=password)
        if user is not None:
            print 'debuglogin_home'
            login(request, user)
            #return redirect(home)
            return redirect(dashboard)
        #else:
        #    messages.warning(request,'Usuario o Contrasenia Incorrecto')

    return render(request, 'login/login.html', None)

# /logout
def logout_view(request):
    logout(request)
    # Redirect to a success page.
    return redirect(login_view)

# /dashboard
@require_http_methods(["GET","POST"])
@login_required(login_url='login')
def dashboard(request):
    userpaymentsErrors = UserPayment.objects.filter(status='RE').count()
    userpaymentsAct = UserPayment.objects.filter(status='RE', user__expiration__gt = date.today()).count()
    userpaymentsDes = UserPayment.objects.filter(status='RE', user__expiration__lte = date.today()).count()

    context = { 'title': 'Dashboard', 'userpaymentserrors': userpaymentsErrors, 'userpaymentsact': userpaymentsAct, 'userpaymentsdes': userpaymentsDes }
    return render(request, 'content/dashboard.html', context)

# /pagos-recurrentes
@require_http_methods(["GET","POST"])
@login_required(login_url='login')
def userpayments(request):

    context = { 'title': 'Pagos Recurrentes' }
    return render(request, 'content/content.html', context)

# /historial-pagos
@require_http_methods(["GET", "POST"])
@login_required(login_url='login')
def paymenthistory(request):

    context = { 'title': 'Historial de Pagos' }
    return render(request, 'content/content.html', context)

# /usuarios
@require_http_methods(["GET", "POST"])
@login_required(login_url='login')
def users(request):

    context = { 'title': 'Usuarios' }
    return render(request, 'content/content.html', context)

# /commercegate
@require_http_methods(["GET", "POST"])
def commercegate(request):
    username = request.GET.get('username')
    email = request.GET.get('email') 
    context = { 'username': username, 'email': email }
    return render(request, 'content/commercegate.html', context)
