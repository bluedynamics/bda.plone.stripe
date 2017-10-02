from bda.plone.shop.interfaces import IShopSettingsProvider
from plone.supermodel import model
from zope import schema
from zope.i18nmessageid import MessageFactory
from zope.interface import provider


_ = MessageFactory('bda.plone.stripe')


@provider(IShopSettingsProvider)
class IStripeSettings(model.Schema):
    """Stripe controlpanel schema.
    """

    model.fieldset(
        'stripe',
        label=_(u'Stripe', default=u'Stripe'),
        fields=[
            'secret_key',
            'publishable_key'
        ],
    )

    secret_key = schema.ASCIILine(
        title=_(u"label_secret_key", default=u'Stripe secret key'),
        required=True,
        default=""
    )

    publishable_key = schema.ASCIILine(
        title=_(u"label_publishable_key", default=u'Stripe publishable key'),
        required=True,
        default=""
    )
