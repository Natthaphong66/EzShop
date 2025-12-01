# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from .models import User

class CustomSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'placeholder': 'รหัสผ่านใหม่'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'placeholder': 'ยืนยันรหัสผ่านใหม่'
        })

class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'placeholder': 'อีเมล'
        })

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': 'ชื่อ'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': 'นามสกุล'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': 'อีเมล'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': 'เบอร์โทรศัพท์'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Tailwind classes to password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'placeholder': 'รหัสผ่าน'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'placeholder': 'ยืนยันรหัสผ่าน'
        })

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'placeholder': 'เบอร์โทรศัพท์'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'placeholder': 'รหัสผ่าน'
        })

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('profile_picture', 'first_name', 'last_name', 'phone', 'email')
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                # ใส่ Class Tailwind เพื่อลบข้อความรกๆ และแต่งปุ่มใหม่
                'class': 'block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
            }),
        }
