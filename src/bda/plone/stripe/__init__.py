from Products.Five import BrowserView
from bda.plone.cart.browser.portlet import SKIP_RENDER_CART_PATTERNS
from bda.plone.cart.cartitem import purge_cart
from bda.plone.payment import Payment
from bda.plone.payment import Payments
from bda.plone.payment.interfaces import IPaymentData
from bda.plone.shop.utils import get_shop_settings
from plone.registry.interfaces import IRegistry
from zExceptions import Redirect
from zope.component import getUtility
from zope.i18nmessageid import MessageFactory
from bda.plone.stripe import interfaces
import logging
import stripe
import sys
import traceback
import transaction


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
    clear_session = False

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
"""


class StripePaymentCheckout(BrowserView, StripeSettings):

    @property
    def checkout_settings(self):
        return CHECKOUT_SETTINGS.format(
            api_key=self.publishable_key,
            order_uid=self.request['uid']
        )


class StripePaymentCharge(BrowserView, StripeSettings):

    def __call__(self):
        stripe.api_key = self.secret_key
        base_url = self.context.absolute_url()
        token = self.request['stripeToken']
        order_uid = self.request['uid']
        payment = Payments(self.context).get('stripe_payment')
        try:
            data = IPaymentData(self.context).data(order_uid)
            amount = data['amount']
            currency = data['currency']
            description = data['description']
            ordernumber = data['ordernumber']
            charge = stripe.Charge.create(
                amount=amount,
                currency=currency,
                description=description,
                source=token,
                metadata={
                    'ordernumber': ordernumber,
                    'order_uid': order_uid
                }
            )
            evt_data = {
                'charge_id': charge['id'],
            }
            payment.succeed(self.request, order_uid, evt_data)
            purge_cart(self.request)
            transaction.commit()
            redirect_url = '{base_url}/@@stripe_payment_success?uid={order_uid}'.format(
                base_url=base_url, order_uid=order_uid)
            return self.request.response.redirect(redirect_url)
        except Redirect as e:
            # simply re-raise error from above, otherwise it would get
            # caught in generel Exception catching block
            raise e
        except stripe.error.CardError as e:
            logger.error(format_traceback())
            body = e.json_body
            err = body.get('error', {})
            logger.error((
                'Failed to charge card\n'
                '    Status: {}\n'
                '    Type: {}\n'
                '    Code: {}\n'
                '    Message: {}'
            ).format(
                e.http_status,
                err.get('type'),
                err.get('code'),
                err.get('message')
            ))
            if not err.get('message'):
                message = 'Failed to charge card'
            else:
                message = err['message']
        except stripe.error.RateLimitError as e:
            logger.error(format_traceback())
            message = 'Too many requests made to the API too quickly'
        except stripe.error.InvalidRequestError as e:
            logger.error(format_traceback())
            message = 'Invalid parameters were supplied to Stripe\'s API'
        except stripe.error.AuthenticationError as e:
            logger.error(format_traceback())
            message = 'Authentication with Stripe\'s API failed'
        except stripe.error.APIConnectionError as e:
            logger.error(format_traceback())
            message = 'Network communication with Stripe failed'
        except stripe.error.StripeError as e:
            logger.error(format_traceback())
            message = 'Generic stripe error'
        except Exception as e:
            logger.error(format_traceback())
            message = 'General error'
        evt_data = {
            'charge_id': 'none',
        }
        payment.failed(self.request, order_uid, evt_data)
        transaction.commit()
        redirect_url = '{}/@@stripe_payment_failed?message={}'.format(
            base_url,
            message
        )
        raise Redirect(redirect_url)


class StripePaymentFailed(BrowserView):

    @property
    def message(self):
        return self.request['message']

    @property
    def shopmaster_mail(self):
        return get_shop_settings().admin_email
