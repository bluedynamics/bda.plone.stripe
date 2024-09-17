from Products.Five import BrowserView
from bda.plone.cart.browser.portlet import SKIP_RENDER_CART_PATTERNS
from bda.plone.payment import Payment
from bda.plone.payment import Payments
from bda.plone.payment.interfaces import IPaymentData
from bda.plone.shop.utils import get_shop_settings
from plone.registry.interfaces import IRegistry
from zExceptions import Redirect
from zope.component import getUtility
from zope.i18nmessageid import MessageFactory
from plone import api
import interfaces
import logging
import stripe
import sys
import traceback
import transaction
import ast
import json

logger = logging.getLogger('bda.plone.stripe')
_ = MessageFactory('bda.plone.stripe')


SKIP_RENDER_CART_PATTERNS.append('@@stripe_payment')
SKIP_RENDER_CART_PATTERNS.append('@@stripe_payment_success')
SKIP_RENDER_CART_PATTERNS.append('@@stripe_payment_failed')


def format_traceback():
    etype, value, tb = sys.exc_info()
    return ''.join(traceback.format_exception(etype, value, tb))


def get_stripe_settings():
    return getUtility(IRegistry).forInterface(interfaces.IStripeSettings)


class StripePayment(Payment):
    pid = 'stripe_payment'
    label = _('stripe_payment', 'Stripe Payment')

    def init_url(self, uid):
        return '%s/@@stripe_payment?uid=%s' % (self.context.absolute_url(), uid)


class StripeSettings(object):

    @property
    def secret_key(self):
        return get_stripe_settings().secret_key

    @property
    def publishable_key(self):
        return get_stripe_settings().publishable_key


CHECKOUT_SETTINGS = """
    var stripe_api_key = '{api_key}';
    var order_uid = '{order_uid}';
    var lang = '{lang}';
"""


class StripePaymentCheckout(BrowserView, StripeSettings):

    @property
    def checkout_settings(self):
        return CHECKOUT_SETTINGS.format(
            api_key=self.publishable_key,
            order_uid=self.request['uid'],
            lang=api.portal.get_current_language()
        )


class StripePaymentCharge(BrowserView, StripeSettings):
    def generate_response(self, intent):
        status = intent['status']
        if status == 'requires_action' or status == 'requires_source_action':
            # Card requires authentication
            json_object = json.dumps({'requiresAction': True, 'paymentIntentId': intent['id'], 'clientSecret': intent['client_secret'], 'status': 'requires_action'})
            return json_object
        elif status == 'requires_payment_method' or status == 'requires_source':
            # Card was not properly authenticated, suggest a new payment method
            json_object = json.dumps({'error': 'Your card was denied, please provide a new payment method', 'status': 'error'})
            return json_object
        elif status == 'succeeded':
            # Payment is complete, authentication not required
            # To cancel the payment you will need to issue a Refund (https://stripe.com/docs/api/refunds)
            print("Payment received!")
            json_object = json.dumps({'clientSecret': intent['client_secret'], 'status': 'succeeded'})
            return json_object

    def __call__(self):
        data = self.request.get('BODY')
        app = self.context.restrictedTraverse('/')  # Zope application server root
        site = app["Plone"]  # your plone instance
        base_url = site.absolute_url()
        payment = Payments(site).get('stripe_payment')
        try:
            data = ast.literal_eval(data)
        except stripe.error.CardError as e:
            return {'error': e.user_message}
        try:
            stripe.api_key = self.secret_key
            infodata = IPaymentData(site).data(data['order_uid'])
            if 'payment_method_id' in data:
                # Create new PaymentIntent with a PaymentMethod ID from the client.
                intent = stripe.PaymentIntent.create(
                    amount=infodata['amount'],
                    currency=infodata['currency'],
                    description=infodata['description'],
                    payment_method=data['payment_method_id'],
                    confirmation_method='manual',
                    confirm=True,
                    # If a mobile client passes `useStripeSdk`, set `use_stripe_sdk=true`
                    # to take advantage of new authentication features in mobile SDKs.
                    use_stripe_sdk=True if 'useStripeSdk' in data and data['useStripeSdk'] else None,
                )
                # After create, if the PaymentIntent's status is succeeded, fulfill the order.
            elif 'payment_intent_id' in data:
                # Confirm the PaymentIntent to finalize payment after handling a required action
                # on the client.
                intent = stripe.PaymentIntent.confirm(data['payment_intent_id'])
                # After confirm, if the PaymentIntent's status is succeeded, fulfill the order.
            intent_resp = self.generate_response(intent)
            try:
                intent_resp_data = json.loads(intent_resp)
            except:
                intent_resp_data = intent_resp
            if intent_resp_data['status'] == 'succeeded':
                evt_data = {
                    'charge_id': intent.id,
                }
                payment.succeed(self.request, data['order_uid'], evt_data)
                transaction.commit()
            elif intent_resp_data['status'] == 'error':
                evt_data = {
                    'charge_id': 'none',
                }
                payment.failed(self.request, data['order_uid'], evt_data)
                transaction.commit()
            else:
                pass
            return intent_resp
        except stripe.error.CardError as e:
            return {'error': e.user_message}


class StripePaymentFailed(BrowserView):

    @property
    def message(self):
        return self.request['message']

    @property
    def shopmaster_mail(self):
        return get_shop_settings().admin_email
