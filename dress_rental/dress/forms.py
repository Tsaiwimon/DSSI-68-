from django import forms
from .models import Shop
from .models import Dress, DressImage


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ["name", "phone", "province", "fee"]

        labels = {
            "name": "ชื่อร้าน",
            "phone": "เบอร์โทรศัพท์",
            "province": "จังหวัด/พื้นที่ให้บริการ",
            "fee": "คำอธิบายร้าน (จุดเด่น/กฎกติกาของร้าน)",
        }

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "border px-3 py-2 rounded-lg w-full",
                "placeholder": "ชื่อร้าน"
            }),
            "phone": forms.TextInput(attrs={
                "class": "border px-3 py-2 rounded-lg w-full",
                "placeholder": "เบอร์โทรศัพท์"
            }),
            "province": forms.TextInput(attrs={
                "class": "border px-3 py-2 rounded-lg w-full",
                "placeholder": "จังหวัด/พื้นที่ให้บริการ"
            }),
            "fee": forms.Textarea(attrs={
                "class": "border px-3 py-2 rounded-lg w-full",
                "placeholder": "คำอธิบายร้าน เช่น จุดเด่น กฎกติกา",
                "rows": 3
            }),
        }


from django.forms import modelformset_factory
from .models import Dress, DressImage

class DressForm(forms.ModelForm):
    class Meta:
        model = Dress
        fields = [
            'name',
            'description',
            'size',
            'daily_price',
            'deposit',
            'stock',
            'categories',
            'is_available',
        ]


class DressImageForm(forms.ModelForm):
    class Meta:
        model = DressImage
        fields = ['image']


DressImageFormSet = modelformset_factory(
    DressImage,
    form=DressImageForm,
    extra=3,
    can_delete=True
)


