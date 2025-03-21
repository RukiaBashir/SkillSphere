from django import forms
from .models import CartItem, Order


class CartItemForm(forms.ModelForm):
    """
    Although adding a CartItem is typically handled by a view (via a button),
    this form can be used if you need to validate or update a CartItem.
    The `class_booking` field is rendered as hidden since it is set by the view,
    and the `amount` is read-only.
    """

    class Meta:
        model = CartItem
        fields = ['class_booking', 'amount']
        widgets = {
            'class_booking': forms.HiddenInput(),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }


class OrderForm(forms.ModelForm):
    """
    This form is used during checkout.
    It displays the total amount (read-only) and can be extended to include additional
    fields if needed (such as payment method confirmation).
    """

    class Meta:
        model = Order
        fields = ['total']
        widgets = {
            'total': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }
