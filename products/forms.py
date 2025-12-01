from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['image', 'name', 'category', 'price', 'description', 'condition']
        
        widgets = {
            # ตกแต่ง Input ทั่วไป (ชื่อ, ราคา)
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors placeholder-slate-400',
                'placeholder': 'เช่น เสื้อยืด Nike สีขาว'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors',
                'placeholder': '0.00'
            }),
            
            # ตกแต่ง Select Box (หมวดหมู่)
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors bg-white cursor-pointer'
            }),
            
            # ตกแต่ง Textarea (รายละเอียด)
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-200 focus:border-black focus:ring-1 focus:ring-black transition-colors min-h-[120px]',
                'placeholder': 'อธิบายรายละเอียดสินค้า ตำหนิ หรือข้อมูลเพิ่มเติม...',
                'rows': 4
            }),
            
            # Radio Button (สภาพสินค้า)
            'condition': forms.RadioSelect(),
            
            # File Input (รูปภาพ) - ซ่อนไว้เพราะเราจะใช้ Label แทน
            'image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*'
            }),
        }

    images = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/*',
            'id': 'id_images'
        }),
        required=False,
        label="รูปภาพสินค้า (สูงสุด 5 รูป)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
