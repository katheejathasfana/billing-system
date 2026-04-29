from django.shortcuts import render,redirect,get_object_or_404
from BILLING.models import *
from django.contrib import messages
from decimal import Decimal
from django.template.loader import get_template
from django.http import HttpResponse
# from xhtml2pdf import pisa
from django.db.models import Q
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


# Create your views here.
@login_required
def invoices(request):
    if 'phone' in request.session:
        del request.session['phone']
    if request.method == "GET":
        search=request.GET.get("search")
        date=request.GET.get("date")
        invoices=Invoice.objects.all().order_by('-id')
        if search:
            invoices=Invoice.objects.filter(Q(customer__fullname__icontains=search)|Q(id__icontains=search)|Q(grand_total__icontains=search))

        elif date:
            invoices=Invoice.objects.filter(date__date=date)

        else:
            invoices=Invoice.objects.all().order_by('-id')
    return render(request,"invoices.html",locals())

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def search_product(request):
    q = request.GET.get('q', '')
    if q:
        products = Product.objects.filter(name__icontains=q, stock__gt=0).values('id', 'name')[:10]
        return JsonResponse(list(products), safe=False)
    return JsonResponse([], safe=False)


@login_required
def add_product_to_cart(request, id):
    phone = request.session.get('phone')
    if not phone:
        messages.error(request, "Customer phone number missing in session.")
        return redirect('create_invoice')

    customer = Customer.objects.filter(phone=phone).first()
    if not customer:
            messages.error(request, "Customer not found.")
            return redirect('create_invoice')


    cart, created = Cart.objects.get_or_create(customer=customer)


    product = get_object_or_404(Product, id=id, stock__gt=0)

    cart_item = CartItem.objects.filter(cart=cart, product=product).first()
    if cart_item:
        if cart_item.quantity < product.stock:
            cart.total -= cart_item.sub_total
            cart_item.quantity += 1
            cart_item.sub_total = product.price * cart_item.quantity
            cart_item.save()
            cart.total += cart_item.sub_total
        else:
            messages.warning(request, f"Only {product.stock} items available.")
            return redirect("create_invoice")
    else:
        cart_item = CartItem.objects.create(product=product, cart=cart)
        cart_item.sub_total = product.price * cart_item.quantity
        cart_item.save()
        cart.total += cart_item.sub_total

    # Update totals
    gst = cart.total * Decimal(cart.gst_percentage / 100)
    cart.gst = gst
    cart.grand_total = cart.total + cart.gst
    cart.save()

    return redirect("create_invoice")


@login_required
def create_invoice(request):
    if request.method == "POST" and request.content_type == "application/json":
        try:
            data = json.loads(request.body)
            phone = data.get('phone')
            if phone:
                request.session['phone'] = phone
                return JsonResponse({'status': 'ok', 'stored_phone': phone})
            else:
                return JsonResponse({'error': 'No phone provided'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        
    phone = request.session.get("phone")
    customers = Customer.objects.all()
    cart=None
    cart_item=None
    balance = 0
    due_amount= 0
    new_wallet_balance = 0
    amount_paid = 0
    products=Product.objects.filter(stock__gt=0)
    # print(products)
    
    if phone:
        customer = Customer.objects.filter(phone=phone).first()

        if customer:
            cart = Cart.objects.filter(customer=customer).first()

            if not cart:
                cart = Cart.objects.create(customer=customer)
        else:
            cart = None
    if cart:
        due = cart.amount_due
        if due<0:
            due_amount=abs(due)
        elif due >= 0:
            balance=abs(due)

            
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_quantity":
            item_id=int(request.POST.get("item_id"))
            quantity=int(request.POST.get("quantity"))
            print("quantity:",quantity)
            cart_item=CartItem.objects.get(id=item_id)
            product_stock = int(cart_item.product.stock)
            if quantity <= product_stock and quantity >= 1:
                cart.total -= cart_item.sub_total

                cart_item.quantity = quantity
                cart_item.sub_total=cart_item.product.price * int(quantity)
                print(cart_item.sub_total)
                cart_item.save()

                cart.total += cart_item.sub_total
                gst=cart.total * Decimal((cart.gst_percentage/100))
                cart.gst = gst
                cart.grand_total = cart.total + cart.gst
                cart.save()
                return redirect('create_invoice')
            else:
                if quantity > product_stock:
                    messages.warning(request, f"Maximum available stock of {cart_item.product} is {product_stock}.")
                    cart.total -= cart_item.sub_total

                    cart_item.quantity = product_stock
                    cart_item.sub_total = cart_item.product.price * product_stock
                    cart_item.save()

                    cart.total += cart_item.sub_total
                    gst=cart.total * Decimal((cart.gst_percentage/100))
                    cart.gst = gst
                    cart.grand_total = cart.total + cart.gst
                    cart.save()
                    return redirect('create_invoice')
                elif quantity < 1:
                    messages.warning(request,f"Quantity for { cart_item.product } was less than 1. It has been reset to 1 automatically.")
                    cart.total -= cart_item.sub_total

                    cart_item.quantity = 1
                    cart_item.sub_total = cart_item.product.price * cart_item.quantity
                    cart_item.save()

                    cart.total += cart_item.sub_total
                    gst=cart.total * Decimal((cart.gst_percentage/100))
                    cart.gst = gst
                    cart.grand_total = cart.total + cart.gst
                    cart.save()
                    return redirect('create_invoice')

            return redirect('create_invoice')


        
        elif action == "remove_product":
            item_id = int(request.POST.get("product_id"))
            print(item_id)
            cart_item=CartItem.objects.get(id=item_id)

            cart.total -= cart_item.sub_total
            gst=cart.total * Decimal((cart.gst_percentage/100))
            cart.gst = gst
            cart.grand_total = cart.total + cart.gst
            cart_item.delete()
            cart.save()
            

            return redirect('create_invoice')  
        
           

        elif action == "payment":
            amount_paid = Decimal(request.POST.get("amount_paid"))

            if cart:
                cart_items = cart.cartitem_set.all()
                if cart_items:
                    grand_total = cart.grand_total
                    customer = cart.customer
                    amount_due = amount_paid-grand_total

                    #if amount_due > 0 = amount_due, which will include in wallet as negative 
                    #else balence, which will include in wallet as positive
                    
                    cart.amount_paid = amount_paid
                    cart.amount_due = amount_due
                    cart.save()


                    messages.success(request,f"Payment recorded.Amount Paid: ₹{amount_paid},  Amount due: ₹{amount_due}, Wallet remaining: ₹{customer.wallet}")
                    return redirect('create_invoice')
                else:
                    messages.error(request,"Did you forget to add a product?")
                    return redirect('create_invoice')
            else:
                messages.error(request,"No cart available")
                return redirect('create_invoice')
        
        elif action == "save_invoice":
            if not phone:
                messages.error(request,"Did you forget to add a customer")
                return redirect('create_invoice')
            if not cart or not cart.cartitem_set.exists():
                messages.error(request,"Cart is empty, Add products before saving.")
                return redirect('create_invoice')
            # if not cart.amount_paid:
            #     messages.error(request,"Did you forget to pay?")
            #     return redirect('create_invoice')

            cart.amount_due = cart.amount_paid - cart.grand_total
            customer = cart.customer
            print(customer)
            print(cart.amount_due)
            new_wallet_balance = customer.wallet - abs(cart.amount_due)
            print(new_wallet_balance)
            if new_wallet_balance < -customer.credit_limit:
                messages.error(request, f"Customer has exceeded their credit limit of ₹{customer.credit_limit}.")
                return redirect('create_invoice')
            
            invoice=Invoice.objects.create(
                customer = cart.customer,
                staff = request.user,
                date=datetime.now(),
                total = cart.total,
                grand_total = cart.grand_total,
                gst=cart.gst,
                amount_paid=cart.amount_paid,
            )

            invoice.amount_due = invoice.amount_paid - invoice.grand_total

            if invoice.amount_due < 0:
                if customer.wallet >= abs(invoice.amount_due):
                    customer.wallet -= abs(invoice.amount_due)
                    invoice.amount_due = 0
                elif customer.wallet < abs(invoice.amount_due):
                    invoice.amount_due += customer.wallet
                    customer.wallet = invoice.amount_due

            elif invoice.amount_due > 0:
                old_dues = Invoice.objects.filter(customer=customer, amount_due__lt=0).exclude(id=invoice.id).order_by('date')
                print("old dues",old_dues)
                if old_dues:
                    customer.wallet += invoice.amount_due

                    for old in old_dues:
                        if invoice.amount_due <= 0:
                            break

                        old_due_abs = abs(old.amount_due)

                        if invoice.amount_due >= old_due_abs:
                            invoice.amount_due =float(invoice.amount_due) - float(old_due_abs)
                            old.amount_due = 0
                        else:
                            old.amount_due =float(old_due_abs) + float(invoice.amount_due)
                            invoice.amount_due = 0

                        old.save()
                        invoice.save()
                    
                else:
                    customer.wallet += invoice.amount_due

            invoice.save()
            customer.save()


              
            for item in CartItem.objects.filter(cart=cart):
                invoice_item=InvoiceItem.objects.create(
                    invoice=invoice,
                    product=item.product,
                    quantity=item.quantity,
                    sub_total=item.sub_total
                )

                item.product.stock -= item.quantity
                item.product.save()
            
            CartItem.objects.filter(cart=cart).delete()
            cart.delete()

            messages.success(request,"Invoice created successfully!")
            return redirect('invoices')
        
        elif action == "clear_invoice":
            if cart:
                cart.delete()
                request.session.pop('phone', None)
                messages.success(request,"Invoice cleared successfully")
                return redirect('create_invoice')
            else:
                messages.error(request,"No invoice to clear")
                return redirect('create_invoice')
         

    cart_items=CartItem.objects.filter(cart=cart).order_by('-created_at')
    return render(request, "create_invoice.html", locals())




@login_required
def new_customer(request):
    if request.method == "POST":
        fullname=request.POST.get("fullname")
        phone=request.POST.get("phone")
        address=request.POST.get("address")

        customer=Customer.objects.filter(phone=phone)
        if not customer:
            Customer.objects.create(
                fullname=fullname,
                phone=phone,
                address=address
            )

            request.session['phone'] = phone

            messages.success(request,"New Customer Added Successfully")
            return redirect('create_invoice')
        else:
            messages.warning(request,"Already have customer with this number")
            return redirect('create_invoice')
    
    return redirect('create_invoice')

@login_required
def search_customer(request):
    q=request.GET.get('q','')
    customer=Customer.objects.filter(phone__icontains=q).values('id','fullname','phone')[:10]
    return JsonResponse(list(customer),safe=False)

   



@login_required
def view_invoice(request,id):
    invoice=Invoice.objects.get(id=id)
    invoiceItem=InvoiceItem.objects.filter(invoice=invoice)
    due = 0
    balance = 0

    print(invoice.amount_due)

    if invoice.amount_due < 0:
        due = abs(invoice.amount_due)
    elif invoice.amount_due > 0:
        balance = invoice.amount_due

    return render(request,"view_invoice.html",locals())


# def render_to_pdf(html_page,context):
#     template = get_template(html_page)
#     html = template.render(context)
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="invoice.pdf"'
#     pisa_status = pisa.CreatePDF(html, dest = response)


#     return response if not pisa_status.err else HttpResponse('Error creating pdf')


def invoice_pdf(request,id):
    invoice=Invoice.objects.get(id=id)
    invoice_item = InvoiceItem.objects.filter(invoice=invoice)
    wallet = invoice.customer.wallet
    total_balance = 0
    total_due = 0

    if wallet < 0:
        total_due = abs(wallet)
    elif wallet > 0:
        total_balance = wallet


    context={
        'request': request,
        'invoice':invoice,
        'invoice_item':invoice_item,
        'total_due':total_due,
        'total_balance':total_balance,
        'wallet':wallet
    }
    return render_to_pdf("invoice_pdf.html",context)

def edit_wallet(request,id):
    customer = Customer.objects.get(id=id)
    invoices = Invoice.objects.filter(customer=customer,amount_due__lt=0).order_by('date')
    print(invoices)
    old_wallet = abs(customer.wallet)
    new_balance = 0
    new_due = 0

    if request.method == "POST":
        payment = request.POST.get("payment")
        print(payment)
        

        customer.wallet += Decimal(payment)


        if customer.wallet >= 0:
            for invoice in invoices:
                invoice.amount_due = 0
                invoice.save()
        else:
            for invoice in invoices:
                payment = Decimal(payment)
                if payment >= abs(invoice.amount_due):
                    invoice.amount_due = 0
                    payment -= abs(invoice.amount_due)
                else:
                    invoice.amount_due += Decimal(payment)
                invoice.save()

        customer.save()
        print(customer.wallet)

        if customer.wallet > 0:
            new_balance = customer.wallet
        elif customer.wallet< 0:
            new_due = abs(customer.wallet)
        else:
            new_balance = 0.00
            new_due = 0.00


        return render(request,'edit_wallet.html',locals())
    return render(request,"edit_wallet.html",locals())


