# accounts/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from .views import (
    SignUpView,
    ProfileView,
    PublicProfileView,
    ProfileUpdateView,
    ProfileDeleteView,
    PasswordChangeView,
    ManageListingsView,
)
from .forms import CustomAuthenticationForm, CustomPasswordResetForm, CustomSetPasswordForm


app_name = "accounts"

urlpatterns = [
        # Auth
    path('register/', SignUpView.as_view(), name='register'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<uuid:user_id>/', PublicProfileView.as_view(), name='public_profile'),
    path('profile/edit/', ProfileUpdateView.as_view(), name='profile_update'),
    path('delete/', ProfileDeleteView.as_view(), name='profile_delete'),
    path('password_change/',PasswordChangeView.as_view(),name='password_change' ),
    path('manage-listings/', ManageListingsView.as_view(), name='manage_listings'),
    
    # Password Reset Views
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
            form_class=CustomPasswordResetForm
        ),
        name='password_reset'
    ),
    path(
        'password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'password_reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
            form_class=CustomSetPasswordForm
        ),
        name='password_reset_confirm'
    ),
    path(
        'password_reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
    # Login และ Logout views
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=CustomAuthenticationForm,
            redirect_authenticated_user=True
        ),
        name='login'
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),
]
