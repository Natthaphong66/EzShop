from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    """Form สำหรับเขียนรีวิว"""
    
    rating = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'hidden'}),
        label='ให้คะแนน'
    )
    
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none',
            'rows': 4,
            'placeholder': 'เขียนรีวิวของคุณ... (ไม่บังคับ)'
        }),
        required=False,
        label='ความคิดเห็น'
    )
    
    class Meta:
        model = Review
        fields = ['rating', 'comment']
