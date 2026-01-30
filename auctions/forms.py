from django import forms
from .models import Auction

class AuctionForm(forms.ModelForm):
    duration_hours = forms.IntegerField(
        min_value=1,
        max_value=2,
        initial=1,
        label="ชั่วโมง",
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'min': '1',
            'max': '2'
        })
    )
    duration_minutes = forms.IntegerField(
        min_value=0,
        max_value=59,
        initial=0,
        label="นาที",
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
            'min': '0',
            'max': '59'
        })
    )

    class Meta:
        model = Auction
        fields = ['starting_price', 'min_increment', 'reserve_price']
        widgets = {
            'starting_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': '0.00'
            }),
            'min_increment': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': 'เช่น 100.00'
            }),
            'reserve_price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': 'ราคาขั้นต่ำที่ยอมขาย (ไม่บังคับ)'
            }),
        }
        labels = {
            'starting_price': 'ราคาเริ่มต้น',
            'min_increment': 'ขั้นต่ำในการประมูลแต่ละครั้ง',
            'reserve_price': 'ราคาสำรอง (Reserve Price)',
        }

    def clean(self):
        cleaned_data = super().clean()
        hours = cleaned_data.get('duration_hours') or 0
        minutes = cleaned_data.get('duration_minutes') or 0
        total_minutes = (hours * 60) + minutes
        if total_minutes < 60 or total_minutes > 120:
            raise forms.ValidationError('ระยะเวลาประมูลต้องอยู่ระหว่าง 1 ถึง 2 ชั่วโมง')
        return cleaned_data
