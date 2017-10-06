================
bda.plone.stripe
================

Stripe payment processor for ``bda.plone.shop``.


Installation
============

This package is part of the ``bda.plone.shop`` stack. Please refer to
``https://github.com/bluedynamics/bda.plone.shop`` for installation
instructions.

Include this package to your setup dependencies and install this package
via Plone control panel add on installation page or add ``bda.plone.stripe``
to install dependencies in your integration package generic setup dependencies.


Configuration
=============

In order to make this payment processor work properly you need to define
the Stripe ``Secret key`` and ``Publishable key``. You can obtain these keys
from https://stripe.com.

You either need to configure these keys in Shop Control Panel under ``Stripe``
of via your integration package generic setup ``registry.xml``


Create translations
===================

::

    $ cd src/bda/plone/stripe/
    $ ./i18n.sh


Contributors
============

- Robert Niederreiter (Author)
- Peter Holzer (Development)
