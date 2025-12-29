from django import forms
from .models import Shop
from .models import Dress, DressImage
from django.forms import modelformset_factory



class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = [
            "name",
            "phone",
            "province",
            "fee",
            "line_id",
            "address",
            "map_url",
            "shop_logo",
            "cover_image",
        ]

        labels = {
            "name": "ชื่อร้าน",
            "phone": "เบอร์โทรศัพท์",
            "province": "จังหวัด/พื้นที่ให้บริการ",
            "fee": "คำอธิบายร้าน (จุดเด่น/กฎกติกาของร้าน)",
            "line_id": "Line ID",
            "address": "ที่อยู่ร้าน",
            "map_url": "ลิงก์แผนที่ร้าน (Google Maps)",
            "shop_logo": "โลโก้ร้าน",
            "cover_image": "รูปปกร้าน",
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
            "line_id": forms.TextInput(attrs={
                "class": "border px-3 py-2 rounded-lg w-full",
                "placeholder": "Line ID"
            }),
            "address": forms.Textarea(attrs={
                "class": "border px-3 py-2 rounded-lg w-full",
                "placeholder": "ที่อยู่ร้าน",
                "rows": 3
            }),
            "map_url": forms.URLInput(attrs={
                "class": "border px-3 py-2 rounded-lg w-full",
                "placeholder": "ลิงก์ Google Maps"
            }),
        }




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


