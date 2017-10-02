from bda.plone.payment import Payment


class StripePayment(Payment):
    pid = 'stripe_payment'
    label = _('stripe_payment', 'Stripe Payment')

    def init_url(self, uid):
        return '%s/@@stripe_payment?uid=%s' % (self.context.absolute_url(), uid)
