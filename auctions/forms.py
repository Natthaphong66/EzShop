from django import forms
from .models import Auction

class AuctionForm(forms.ModelForm):
    class Meta:
        model = Auction
        fields = ['starting_price', 'min_increment', 'reserve_price', 'end_at']
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
            'end_at': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'type': 'datetime-local'
            }),
        }
        labels = {
            'starting_price': 'ราคาเริ่มต้น',
            'min_increment': 'ขั้นต่ำในการประมูลแต่ละครั้ง',
            'reserve_price': 'ราคาสำรอง (Reserve Price)',
            'end_at': 'เวลาจบประมูล',
        }
